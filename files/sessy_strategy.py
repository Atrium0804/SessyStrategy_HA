"""
Sessy Charging Strategy — AppDaemon app
Runs every 5 minutes and sets the optimal battery setpoint.

All tunables and entity IDs are configured in apps.yaml (see README) and read
in initialize(); the literals below are only fallback defaults.

Strategy (priority order):
  1. Excessive price (raw > price_discharge): battery setpoint, discharge toward SOC floor
  2. Negative/very cheap price (raw < price_charge): battery setpoint, charge toward ceiling,
     rate spread over the remaining run of cheap-price hours
  3. Pre-peak window, SOC < target, and the expected evening peak beats the current
     import price by min_arbitrage_margin: battery setpoint, charge toward SOC target
  4. Default: grid setpoint = 0W (absorb solar, block export)
"""

import appdaemon.plugins.hass.hassapi as hass
from datetime import timedelta


class SessyStrategy(hass.Hass):

    def initialize(self):
        # ── Tunables (overridable from apps.yaml) ───────────────────────────
        self.capacity_wh          = float(self.args.get("capacity_wh", 5000))
        self.max_power_w          = float(self.args.get("max_power_w", 2200))
        self.soc_target           = float(self.args.get("soc_target", 90))
        self.soc_floor            = float(self.args.get("soc_floor", 20))
        self.cheap_soc_target     = float(self.args.get("cheap_soc_target", 100))
        self.surcharge            = float(self.args.get("surcharge", 0.11))
        self.price_discharge      = float(self.args.get("price_discharge", 0.39))
        self.price_charge         = float(self.args.get("price_charge", -0.10))
        self.prepeak_start        = int(self.args.get("prepeak_start", 16))
        self.prepeak_end          = int(self.args.get("prepeak_end", 18))
        self.prepeak_window_h     = float(self.args.get("prepeak_window_h", 2.0))
        # Adaptive spread window: charge/discharge is spread over the contiguous run
        # of hours the price stays past the threshold, floored at min_window_h.
        # Wider spread = lower power = lower round-trip losses.
        self.min_window_h         = float(self.args.get("min_window_h", 2.0))
        # Seconds to wait after a live input changes before re-running, so a slider
        # drag coalesces into a single run instead of one per intermediate value.
        self.rerun_debounce_s     = float(self.args.get("rerun_debounce_s", 2.0))
        self.evening_peak_start   = int(self.args.get("evening_peak_start", 18))
        self.evening_peak_end     = int(self.args.get("evening_peak_end", 23))
        self.min_arbitrage_margin = float(self.args.get("min_arbitrage_margin", 0.05))

        # ── Seasonal operation mode ─────────────────────────────────────────
        # season_mode: auto | summer | winter
        self.season_mode          = str(self.args.get("season_mode", "auto")).strip().lower()
        self.season_day_start     = int(self.args.get("season_day_start", 8))
        self.season_day_end       = int(self.args.get("season_day_end", 18))
        self.season_auto_fallback = str(self.args.get("season_auto_fallback", "winter")).strip().lower()
        # Optional winter-specific overrides. If omitted, base values above are used.
        self.soc_floor_winter       = self._optional_float_arg("soc_floor_winter")
        self.prepeak_start_winter   = self._optional_int_arg("prepeak_start_winter")
        self.prepeak_end_winter     = self._optional_int_arg("prepeak_end_winter")
        self.prepeak_window_h_winter = self._optional_float_arg("prepeak_window_h_winter")

        # ── Entity IDs (overridable from apps.yaml) ─────────────────────────
        self.strategy_select  = self.args.get("strategy_select",  "select.sessy_battery_alt9_power_strategy")
        self.grid_target      = self.args.get("grid_target",      "number.sessy_pwkn_grid_target")
        self.battery_setpoint = self.args.get("battery_setpoint", "number.sessy_battery_alt9_power_setpoint")
        self.soc_sensor       = self.args.get("soc_sensor",       "sensor.sessy_battery_alt9_state_of_charge")
        self.price_sensor     = self.args.get("price_sensor",     "sensor.sessy_dnhh_energy_price")
        self.status_sensor    = self.args.get("status_sensor",    "sensor.sessy_strategy_status")

        # ── Operating-mode selector (input_select) ──────────────────────────
        # The single master control the app obeys. Options are normalised to: optimized | grid_setpoint |
        # battery_setpoint | sessy_dynamic | idle (case- and space-insensitive).
        #   optimized       — run the full price-optimisation priority chain
        #   grid_setpoint   — pass user's grid target through (strategy → nom)
        #   battery_setpoint— pass user's battery power through (strategy → api)
        #   sessy_dynamic   — stand down, hand control to Sessy's own schedule
        #   idle            — stand down, park the battery
        self.mode_select       = self.args.get("mode_select")
        # Single manual setpoint (W). The mode decides where it is applied:
        # grid_setpoint writes it to the grid target, battery_setpoint to the
        # battery power.
        self.setpoint_entity   = self.args.get("setpoint_entity")
        # Sessy power_strategy option strings to select when handing control back.
        # Defaults match the ha-sessy integration; override if your build differs.
        self.sessy_dynamic_option = str(self.args.get("sessy_dynamic_option", "roi"))
        self.idle_option          = str(self.args.get("idle_option", "idle"))
        self.eco_option           = str(self.args.get("eco_option", "eco"))

        # Optional live-tuning helpers (input_number). If set, these override the
        # corresponding static default each cycle, so the value can be changed
        # from the HA UI without restarting AppDaemon.
        self.soc_target_entity           = self.args.get("soc_target_entity")
        self.soc_floor_entity            = self.args.get("soc_floor_entity")
        self.price_discharge_entity      = self.args.get("price_discharge_entity")
        self.price_charge_entity         = self.args.get("price_charge_entity")
        self.min_arbitrage_margin_entity = self.args.get("min_arbitrage_margin_entity")
        self.cheap_soc_target_entity     = self.args.get("cheap_soc_target_entity")
        # Optional live season mode selector (input_select with auto/summer/winter)
        self.season_mode_entity          = self.args.get("season_mode_entity")

        self._last_active_season = None
        self._rerun_timer = None

        self.log("Sessy strategy starting up")
        # Run immediately, then every 5 minutes
        self.run_every(self.update_strategy, "now", 5 * 60)

        # Re-run immediately when the user changes any live input, so tweaks take
        # effect without waiting for the next 5-minute cycle. None entries (unset
        # optional entities) are skipped.
        live_inputs = [
            self.mode_select,
            self.setpoint_entity,
            self.soc_target_entity,
            self.soc_floor_entity,
            self.cheap_soc_target_entity,
            self.price_discharge_entity,
            self.price_charge_entity,
            self.min_arbitrage_margin_entity,
            self.season_mode_entity,
        ]
        for entity in live_inputs:
            if entity:
                self.listen_state(self._on_input_change, entity)

    # ── Main logic ────────────────────────────────────────────────────────────

    def update_strategy(self, kwargs):
        # ── Mode dispatch: the selector is the single master input ──────────
        # Manual and stand-down modes return early; only "optimized" runs the
        # price-optimisation priority chain below.
        mode = self._active_mode()

        if mode == "disabled":
            self.log("Strategy disabled — skipping this cycle")
            return

        if mode == "idle":
            self._apply_standby(self.idle_option, "idle")
            return

        if mode == "sessy_dynamic":
            self._apply_standby(self.sessy_dynamic_option, "sessy_dynamic")
            return

        if mode == "eco":
            self._apply_standby(self.eco_option, "eco")
            return

        if mode == "grid_setpoint":
            watts = self._tunable(0, self.setpoint_entity)
            self.log(f"MANUAL grid setpoint {watts:.0f}W")
            self._set_grid_setpoint(watts)
            self._publish_branch("manual_grid", setpoint=watts)
            return

        if mode == "battery_setpoint":
            watts = self._tunable(0, self.setpoint_entity)
            self.log(f"MANUAL battery setpoint {watts:.0f}W")
            self._set_battery_setpoint(watts)
            self._publish_branch("manual_battery", setpoint=watts)
            return

        # ── mode == "optimized": price-optimisation priority chain ──────────
        now_hour = self.datetime().hour
        soc      = self._get_soc()
        price    = self._get_current_price()

        if soc is None or price is None:
            self.log("Could not read SOC or price — skipping this cycle", level="WARNING")
            return

        import_price = price + self.surcharge
        self.log(
            f"Hour={now_hour:02d}  SOC={soc:.0f}%  "
            f"Raw price={price:.5f}  Import price={import_price:.5f}"
        )

        # Resolve live-tunable values (input_number overrides, else apps.yaml default)
        soc_target           = self._tunable(self.soc_target, self.soc_target_entity)
        soc_floor            = self._tunable(self.soc_floor, self.soc_floor_entity)
        cheap_soc_target     = self._tunable(self.cheap_soc_target, self.cheap_soc_target_entity)
        price_discharge      = self._tunable(self.price_discharge, self.price_discharge_entity)
        price_charge         = self._tunable(self.price_charge, self.price_charge_entity)
        min_arbitrage_margin = self._tunable(self.min_arbitrage_margin, self.min_arbitrage_margin_entity)
        active_season        = self._active_season_mode()
        min_price_hour, min_price_value = self._daily_min_price_hour_and_value()
        if active_season != self._last_active_season:
            self.log(f"Season mode active: {active_season}")
            self._last_active_season = active_season

        soc_floor        = self._seasonal_value(soc_floor, active_season, self.soc_floor_winter)
        prepeak_start    = self._seasonal_value(self.prepeak_start, active_season, self.prepeak_start_winter)
        prepeak_end      = self._seasonal_value(self.prepeak_end, active_season, self.prepeak_end_winter)
        prepeak_window_h = self._seasonal_value(self.prepeak_window_h, active_season, self.prepeak_window_h_winter)

        # Common status fields; the decided branch is attached at each return.
        status_fields = dict(
            active_season=active_season,
            min_price_hour=min_price_hour,
            min_price_value=min_price_value,
            soc=soc,
            raw_price=price,
            import_price=import_price,
            soc_target=soc_target,
            soc_floor=soc_floor,
            cheap_soc_target=cheap_soc_target,
            price_discharge=price_discharge,
            price_charge=price_charge,
            min_arbitrage_margin=min_arbitrage_margin,
            prepeak_start=prepeak_start,
            prepeak_end=prepeak_end,
            prepeak_window_h=prepeak_window_h,
        )

        # ── Priority 1: excessive price → discharge ─────────────────────
        if price > price_discharge:
            window_h    = self._spread_window_h(price_discharge, above=True)
            discharge_w = self._discharge_setpoint(soc, soc_floor, window_h)
            self.log(
                f"DISCHARGE override: import price {import_price:.3f} > "
                f"{price_discharge + self.surcharge:.2f} — "
                f"battery setpoint {discharge_w:.0f}W (SOC {soc:.0f}% → floor {soc_floor:.0f}% "
                f"over {window_h:.2f}h)"
            )
            self._publish_status("discharge", **status_fields)
            self._set_battery_setpoint(discharge_w)
            return

        # ── Priority 2: very cheap / negative price → charge toward ceiling ──
        if price < price_charge:
            if soc >= cheap_soc_target:
                self.log(
                    f"CHEAP CHARGE: SOC {soc:.0f}% already at ceiling "
                    f"{cheap_soc_target:.0f}% — holding grid setpoint 0W"
                )
                self._publish_status("cheap_charge_full", **status_fields)
                self._set_grid_setpoint(0)
                return
            window_h = self._spread_window_h(price_charge, above=False)
            charge_w = self._cheap_charge_setpoint(soc, cheap_soc_target, window_h)
            self.log(
                f"CHEAP CHARGE: raw price {price:.5f} < {price_charge} — "
                f"battery setpoint -{charge_w:.0f}W (SOC {soc:.0f}% → {cheap_soc_target:.0f}% "
                f"over {window_h:.2f}h cheap window)"
            )
            self._publish_status("cheap_charge", **status_fields)
            self._set_battery_setpoint(-charge_w)
            return

        # ── Priority 3: pre-peak charge window ───────────────────────────────
        if prepeak_start <= now_hour < prepeak_end:
            if soc >= soc_target:
                self.log(
                    f"PRE-PEAK: SOC {soc:.0f}% already at target {soc_target:.0f}% — "
                    f"holding grid setpoint 0W"
                )
                self._publish_status("prepeak_full", **status_fields)
                self._set_grid_setpoint(0)
                return

            # Break-even guard: only charge if the best remaining raw price today beats the
            # current raw price by at least min_arbitrage_margin. Both sides are compared
            # as raw prices so the import surcharge cancels out instead of shrinking the margin.
            expected_peak = self._max_price_in_window(now_hour, 24)
            if expected_peak is not None and \
                    (expected_peak - price) < min_arbitrage_margin:
                self.log(
                    f"PRE-PEAK SKIP: best remaining price {expected_peak:.3f} vs current "
                    f"{price:.3f} (spread < margin {min_arbitrage_margin}) — "
                    f"holding grid setpoint 0W"
                )
                self._publish_status("prepeak_skip", **status_fields)
                self._set_grid_setpoint(0)
                return

            charge_w = self._charge_setpoint(soc, soc_target, prepeak_window_h)
            self.log(
                f"PRE-PEAK CHARGE: battery setpoint -{charge_w:.0f}W "
                f"(SOC {soc:.0f}% → target {soc_target:.0f}% over {prepeak_window_h}h)"
            )
            self._publish_status("prepeak_charge", **status_fields)
            self._set_battery_setpoint(-charge_w)   # negative = charge
            return

        # ── Priority 4: evening peak excess discharge ────────────────────────
        if self.evening_peak_start <= now_hour < self.evening_peak_end and soc > soc_target:
            max_remaining_price = self._max_price_in_window(now_hour, 24)
            if max_remaining_price is None or max_remaining_price < price_discharge:
                now_dt = self.datetime()
                peak_end_minutes = self.evening_peak_end * 60
                now_minutes = now_dt.hour * 60 + now_dt.minute
                hours_remaining = (peak_end_minutes - now_minutes) / 60
                discharge_w = self._evening_peak_excess_setpoint(soc, soc_target, hours_remaining)
                # Grid setpoint (negative = export) so the battery covers household
                # load AND the export target. A high home load makes the battery
                # work harder instead of pulling the shortfall from the grid.
                self.log(
                    f"EVENING PEAK EXCESS: SOC {soc:.0f}% > target {soc_target:.0f}% — "
                    f"grid export setpoint -{discharge_w:.0f}W "
                    f"(spread over {hours_remaining:.2f}h remaining peak window)"
                )
                self._publish_status("evening_peak_excess", **status_fields)
                self._set_grid_setpoint(-discharge_w)
                return

        # ── Priority 5: default — grid setpoint 0W (solar absorption) ────────
        self.log("DEFAULT: grid setpoint 0W — absorb solar, block export")
        self._publish_status("default", **status_fields)
        self._set_grid_setpoint(0)

    # ── Mode helpers ──────────────────────────────────────────────────────────

    _VALID_MODES = ("optimized", "grid_setpoint", "battery_setpoint",
                    "sessy_dynamic", "eco", "idle")

    def _active_mode(self) -> str:
        """
        Resolve the operating mode from the input_select selector, normalising
        labels like "Grid setpoint" to "grid_setpoint".
        """
        if self.mode_select:
            state = self.get_state(self.mode_select)
            if isinstance(state, str):
                key = state.strip().lower().replace(" ", "_")
                if key in self._VALID_MODES:
                    return key
        return "optimized"

    def _apply_standby(self, strategy_option: str, branch: str):
        """
        Hand control back to a Sessy power_strategy option (e.g. its own dynamic
        schedule or idle) without writing any setpoint. Only switches the select
        if it is not already on the requested option.
        """
        current = self.get_state(self.strategy_select)
        if current != strategy_option:
            self.call_service(
                "select/select_option",
                entity_id=self.strategy_select,
                option=strategy_option,
            )
            self.log(f"Strategy → {strategy_option} ({branch})")
        self._publish_branch(branch, sessy_strategy=strategy_option)

    # ── Live-input re-run ──────────────────────────────────────────────────────

    def _on_input_change(self, entity, attribute, old, new, kwargs):
        """
        listen_state callback: schedule a strategy re-run after a live input
        changes. Resets a shared debounce timer so a burst of changes (a slider
        drag) collapses into a single run rerun_debounce_s after the last one.
        """
        if old == new:
            return
        if self._rerun_timer is not None:
            self.cancel_timer(self._rerun_timer)
        self.log(f"Input {entity} changed {old} → {new} — re-running in {self.rerun_debounce_s:.0f}s")
        self._rerun_timer = self.run_in(self._rerun_now, self.rerun_debounce_s)

    def _rerun_now(self, kwargs):
        self._rerun_timer = None
        self.update_strategy({})

    # ── Setpoint calculators ──────────────────────────────────────────────────

    def _charge_setpoint(self, soc: float, soc_target: float, prepeak_window_h: float) -> float:
        """
        Watts to charge. Spreads remaining gap over prepeak_window_h.
        Clamped at max_power_w; the Sessy enforces its own hardware limit below that.
        """
        gap_wh   = (soc_target - soc) / 100.0 * self.capacity_wh
        spread_w = gap_wh / prepeak_window_h
        return max(50, min(spread_w, self.max_power_w))

    def _discharge_setpoint(self, soc: float, soc_floor: float, window_h: float) -> float:
        """
        Watts to discharge. Spreads available energy above floor over window_h.
        Clamped at max_power_w; the Sessy enforces its own hardware limit below that.
        """
        available_wh = (soc - soc_floor) / 100.0 * self.capacity_wh
        if available_wh <= 0:
            self.log(f"SOC {soc:.0f}% already at floor {soc_floor:.0f}% — holding 0W")
            return 0
        spread_w = available_wh / window_h
        return max(50, min(spread_w, self.max_power_w))

    def _cheap_charge_setpoint(self, soc: float, cheap_soc_target: float, window_h: float) -> float:
        """
        Watts to charge from the grid during a cheap-price window.
        Spreads the gap to cheap_soc_target over window_h, so a short dip charges
        hard and a long cheap block charges gently.
        Clamped at max_power_w; the Sessy enforces its own hardware limit below that.
        """
        if soc >= cheap_soc_target:
            return 0
        gap_wh   = (cheap_soc_target - soc) / 100.0 * self.capacity_wh
        spread_w = gap_wh / window_h
        return max(50, min(spread_w, self.max_power_w))

    def _evening_peak_excess_setpoint(self, soc: float, soc_target: float, hours_remaining: float) -> float:
        """
        Watts of excess SOC above target to sell, spread over remaining peak hours.
        Applied as a negative grid setpoint (negative = export), so the battery
        covers household load on top of the export and never imports to top up.
        Clamped at max_power_w; the Sessy enforces its own hardware limit below that.
        """
        gap_wh   = (soc - soc_target) / 100.0 * self.capacity_wh
        spread_w = gap_wh / max(hours_remaining, 0.083)  # avoid div/0
        return max(50, min(spread_w, self.max_power_w))

    # ── Actuator helpers ─────────────────────────────────────────────────────

    def _set_grid_setpoint(self, watts: float):
        """Switch to NOM strategy and set grid target (positive = import, negative = export)."""
        current_strategy = self.get_state(self.strategy_select)
        if current_strategy != "nom":
            self.call_service(
                "select/select_option",
                entity_id=self.strategy_select,
                option="nom"
            )
            self.log("Strategy → nom (grid setpoint)")
        self.call_service(
            "number/set_value",
            entity_id=self.grid_target,
            value=int(round(watts))
        )

    def _set_battery_setpoint(self, watts: float):
        """
        Switch to API strategy and set battery power setpoint.
        Positive = discharge, negative = charge.
        """
        current_strategy = self.get_state(self.strategy_select)
        if current_strategy != "api":
            self.call_service(
                "select/select_option",
                entity_id=self.strategy_select,
                option="api"
            )
            self.log("Strategy → api (battery setpoint)")
        self.call_service(
            "number/set_value",
            entity_id=self.battery_setpoint,
            value=int(round(watts))
        )

    # ── Sensor readers ────────────────────────────────────────────────────────

    def _tunable(self, default: float, entity_id) -> float:
        """
        Return the live value from an optional input_number helper, or the
        static apps.yaml default when no helper is configured or readable.
        """
        if not entity_id:
            return default
        try:
            return float(self.get_state(entity_id))
        except (TypeError, ValueError):
            return default

    def _optional_float_arg(self, key: str) -> float | None:
        value = self.args.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _optional_int_arg(self, key: str) -> int | None:
        value = self.args.get(key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _seasonal_value(self, base_value, active_season: str, winter_override):
        if active_season == "winter" and winter_override is not None:
            return winter_override
        return base_value

    def _active_season_mode(self) -> str:
        mode = self.season_mode
        if self.season_mode_entity:
            mode_state = self.get_state(self.season_mode_entity)
            if isinstance(mode_state, str):
                mode = mode_state.strip().lower()

        if mode in ("summer", "winter"):
            return mode

        inferred = self._infer_season_from_price_minimum()
        if inferred:
            return inferred

        return "summer" if self.season_auto_fallback == "summer" else "winter"

    def _infer_season_from_price_minimum(self) -> str | None:
        """
        Infer season from today's lowest raw price hour.
        If the minimum is during daytime [season_day_start, season_day_end),
        treat it as summer; otherwise winter.
        """
        min_hour, _ = self._daily_min_price_hour_and_value()
        if min_hour is None:
            return None

        if self.season_day_start <= min_hour < self.season_day_end:
            return "summer"
        return "winter"

    def _daily_min_price_hour_and_value(self):
        prices = self._get_prices_dict()
        if not prices:
            return None, None

        today = self.datetime().strftime("%Y-%m-%d")
        min_price = None
        min_hour = None
        for hour in range(24):
            key = f"{today}T{hour:02d}:00:00"
            if key not in prices:
                continue
            try:
                value = float(prices[key])
            except (TypeError, ValueError):
                continue
            if min_price is None or value < min_price:
                min_price = value
                min_hour = hour

        return min_hour, min_price

    def _publish_status(
            self,
            active_branch: str,
            active_season: str,
            min_price_hour,
            min_price_value,
            soc: float,
            raw_price: float,
            import_price: float,
            soc_target: float,
            soc_floor: float,
            cheap_soc_target: float,
            price_discharge: float,
            price_charge: float,
            min_arbitrage_margin: float,
            prepeak_start: int,
            prepeak_end: int,
            prepeak_window_h: float,
    ):
        if not self.status_sensor:
            return

        mode_source = self.season_mode
        if self.season_mode_entity:
            mode_state = self.get_state(self.season_mode_entity)
            if isinstance(mode_state, str):
                mode_source = mode_state.strip().lower()

        if mode_source not in ("auto", "summer", "winter"):
            mode_source = "auto"

        self.set_state(
            self.status_sensor,
            state=active_season,
            attributes={
                "active_branch": active_branch,
                "season_mode_source": mode_source,
                "season_day_start": self.season_day_start,
                "season_day_end": self.season_day_end,
                "season_auto_fallback": self.season_auto_fallback,
                "daily_min_price_hour": min_price_hour,
                "daily_min_price": min_price_value,
                "soc": round(soc, 2),
                "raw_price": round(raw_price, 5),
                "import_price": round(import_price, 5),
                "soc_target": soc_target,
                "soc_floor": soc_floor,
                "cheap_soc_target": cheap_soc_target,
                "price_discharge": price_discharge,
                "price_charge": price_charge,
                "min_arbitrage_margin": min_arbitrage_margin,
                "prepeak_start": prepeak_start,
                "prepeak_end": prepeak_end,
                "prepeak_window_h": prepeak_window_h,
            },
        )

    def _publish_branch(self, active_branch: str, **extra):
        """
        Lightweight status publish for manual and stand-down modes, where the
        full optimisation context (season, thresholds) does not apply. Sets the
        status state to the active branch and records any extra fields.
        """
        if not self.status_sensor:
            return
        self.set_state(
            self.status_sensor,
            state=active_branch,
            attributes={"active_branch": active_branch, **extra},
        )

    def _get_soc(self) -> float | None:
        state = self.get_state(self.soc_sensor)
        try:
            return float(state)
        except (TypeError, ValueError):
            return None

    def _get_current_price(self) -> float | None:
        """
        Read the current hour's raw export price from the energy_prices attribute.
        Falls back to the sensor state if the attribute lookup fails.
        """
        try:
            prices = self.get_state(self.price_sensor, attribute="energy_prices")
            if prices:
                now_key = self.datetime().strftime("%Y-%m-%dT%H:00:00")
                if now_key in prices:
                    return float(prices[now_key])
            # Fallback: sensor state is already the current price
            return float(self.get_state(self.price_sensor))
        except (TypeError, ValueError, KeyError):
            return None

    def _get_prices_dict(self):
        """Return the energy_prices attribute dict, or None if unavailable."""
        try:
            prices = self.get_state(self.price_sensor, attribute="energy_prices")
            return prices if prices else None
        except (TypeError, ValueError):
            return None

    def _contiguous_price_hours(self, threshold: float, above: bool) -> int:
        """
        Count consecutive upcoming hours (including the current one) whose raw price
        stays past threshold — above it when above=True, below it when above=False.
        The run stops at the first hour that crosses back. Returns at least 1.
        """
        prices = self._get_prices_dict()
        if not prices:
            return 1
        cursor = self.datetime().replace(minute=0, second=0, microsecond=0)
        count  = 0
        for _ in range(48):
            key = cursor.strftime("%Y-%m-%dT%H:00:00")
            if key not in prices:
                break
            try:
                price = float(prices[key])
            except (TypeError, ValueError):
                break
            if (price > threshold) if above else (price < threshold):
                count += 1
            else:
                break
            cursor += timedelta(hours=1)
        return max(count, 1)

    def _spread_window_h(self, threshold: float, above: bool) -> float:
        """
        Adaptive spread window in hours: the contiguous run of upcoming hours the
        price stays past threshold, floored at min_window_h.
        """
        run_h = self._contiguous_price_hours(threshold, above)
        return max(run_h, self.min_window_h)

    def _max_price_in_window(self, start_hour: int, end_hour: int) -> float | None:
        """
        Return the maximum raw price across today's [start_hour, end_hour) slots,
        or None if no price data is available for that window.
        """
        prices = self._get_prices_dict()
        if not prices:
            return None
        today  = self.datetime().strftime("%Y-%m-%d")
        values = []
        for hour in range(start_hour, end_hour):
            key = f"{today}T{hour:02d}:00:00"
            if key in prices:
                try:
                    values.append(float(prices[key]))
                except (TypeError, ValueError):
                    continue
        return max(values) if values else None
