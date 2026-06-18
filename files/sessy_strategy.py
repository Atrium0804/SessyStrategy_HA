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
        self.c_rate_cap           = float(self.args.get("c_rate_cap", 0.40))
        self.soc_target           = float(self.args.get("soc_target", 90))
        self.soc_floor            = float(self.args.get("soc_floor", 20))
        self.cheap_soc_target     = float(self.args.get("cheap_soc_target", 100))
        self.surcharge            = float(self.args.get("surcharge", 0.11))
        self.price_discharge      = float(self.args.get("price_discharge", 0.39))
        self.price_charge         = float(self.args.get("price_charge", -0.10))
        self.prepeak_start        = int(self.args.get("prepeak_start", 16))
        self.prepeak_end          = int(self.args.get("prepeak_end", 18))
        self.prepeak_window_h     = float(self.args.get("prepeak_window_h", 2.0))
        self.discharge_window_h   = float(self.args.get("discharge_window_h", 2.0))
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
        # Optional master enable switch (input_boolean). If unset, the app always runs.
        self.enable_switch    = self.args.get("enable_switch")

        # Optional live-tuning helpers (input_number). If set, these override the
        # corresponding static default each cycle, so the value can be changed
        # from the HA UI without restarting AppDaemon.
        self.soc_target_entity           = self.args.get("soc_target_entity")
        self.soc_floor_entity            = self.args.get("soc_floor_entity")
        self.price_discharge_entity      = self.args.get("price_discharge_entity")
        self.price_charge_entity         = self.args.get("price_charge_entity")
        self.min_arbitrage_margin_entity = self.args.get("min_arbitrage_margin_entity")
        # Optional live season mode selector (input_select with auto/summer/winter)
        self.season_mode_entity          = self.args.get("season_mode_entity")

        self._last_active_season = None

        self.log("Sessy strategy starting up")
        # Run immediately, then every 5 minutes
        self.run_every(self.update_strategy, "now", 5 * 60)

    # ── Main logic ────────────────────────────────────────────────────────────

    def update_strategy(self, kwargs):
        if self.enable_switch and self.get_state(self.enable_switch) == "off":
            self.log("Strategy disabled via enable switch — skipping this cycle")
            return

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

        self._publish_status(
            active_season=active_season,
            min_price_hour=min_price_hour,
            min_price_value=min_price_value,
            soc=soc,
            raw_price=price,
            import_price=import_price,
            soc_target=soc_target,
            soc_floor=soc_floor,
            price_discharge=price_discharge,
            price_charge=price_charge,
            min_arbitrage_margin=min_arbitrage_margin,
            prepeak_start=prepeak_start,
            prepeak_end=prepeak_end,
            prepeak_window_h=prepeak_window_h,
        )

        # ── Priority 1: excessive price → discharge ─────────────────────
        if price > price_discharge:
            discharge_w = self._discharge_setpoint(soc, soc_floor)
            self.log(
                f"DISCHARGE override: import price {import_price:.3f} > "
                f"{price_discharge + self.surcharge:.2f} — "
                f"battery setpoint {discharge_w:.0f}W (SOC {soc:.0f}% → floor {soc_floor:.0f}%)"
            )
            self._set_battery_setpoint(discharge_w)
            return

        # ── Priority 2: very cheap / negative price → charge toward ceiling ──
        if price < price_charge:
            if soc >= self.cheap_soc_target:
                self.log(
                    f"CHEAP CHARGE: SOC {soc:.0f}% already at ceiling "
                    f"{self.cheap_soc_target:.0f}% — holding grid setpoint 0W"
                )
                self._set_grid_setpoint(0)
                return
            cheap_hours = self._count_cheap_hours(price_charge)
            charge_w    = self._cheap_charge_setpoint(soc, cheap_hours)
            self.log(
                f"CHEAP CHARGE: raw price {price:.5f} < {price_charge} — "
                f"battery setpoint -{charge_w:.0f}W (SOC {soc:.0f}% → {self.cheap_soc_target:.0f}% "
                f"over {cheap_hours}h cheap window)"
            )
            self._set_battery_setpoint(-charge_w)
            return

        # ── Priority 3: pre-peak charge window ───────────────────────────────
        if prepeak_start <= now_hour < prepeak_end:
            if soc >= soc_target:
                self.log(
                    f"PRE-PEAK: SOC {soc:.0f}% already at target {soc_target:.0f}% — "
                    f"holding grid setpoint 0W"
                )
                self._set_grid_setpoint(0)
                return

            # Break-even guard: only charge if the expected evening peak beats the
            # current import price by at least min_arbitrage_margin.
            expected_peak = self._max_price_in_window(self.evening_peak_start, self.evening_peak_end)
            if expected_peak is not None and \
                    (expected_peak - import_price) < min_arbitrage_margin:
                self.log(
                    f"PRE-PEAK SKIP: expected peak {expected_peak:.3f} vs import now "
                    f"{import_price:.3f} (spread < margin {min_arbitrage_margin}) — "
                    f"holding grid setpoint 0W"
                )
                self._set_grid_setpoint(0)
                return

            charge_w = self._charge_setpoint(soc, soc_target, prepeak_window_h)
            self.log(
                f"PRE-PEAK CHARGE: battery setpoint -{charge_w:.0f}W "
                f"(SOC {soc:.0f}% → target {soc_target:.0f}% over {prepeak_window_h}h)"
            )
            self._set_battery_setpoint(-charge_w)   # negative = charge
            return

        # ── Priority 4: default — grid setpoint 0W (solar absorption) ────────
        self.log("DEFAULT: grid setpoint 0W — absorb solar, block export")
        self._set_grid_setpoint(0)

    # ── Setpoint calculators ──────────────────────────────────────────────────

    def _charge_setpoint(self, soc: float, soc_target: float, prepeak_window_h: float) -> float:
        """
        Watts to charge. Spreads remaining gap over prepeak_window_h.
        Capped at c_rate_cap × capacity and max_power_w.
        """
        gap_wh   = (soc_target - soc) / 100.0 * self.capacity_wh
        spread_w = gap_wh / prepeak_window_h
        cap_w    = self.c_rate_cap * self.capacity_wh
        return max(50, min(spread_w, cap_w, self.max_power_w))

    def _discharge_setpoint(self, soc: float, soc_floor: float) -> float:
        """
        Watts to discharge. Spreads available energy above floor over discharge_window_h.
        Capped at c_rate_cap × capacity and max_power_w.
        """
        available_wh = (soc - soc_floor) / 100.0 * self.capacity_wh
        if available_wh <= 0:
            self.log(f"SOC {soc:.0f}% already at floor {soc_floor:.0f}% — holding 0W")
            return 0
        spread_w = available_wh / self.discharge_window_h
        cap_w    = self.c_rate_cap * self.capacity_wh
        return max(50, min(spread_w, cap_w, self.max_power_w))

    def _cheap_charge_setpoint(self, soc: float, cheap_hours: int) -> float:
        """
        Watts to charge from the grid during a cheap-price window.
        Spreads the gap to cheap_soc_target over the number of remaining cheap
        hours, so a short dip charges hard and a long cheap block charges gently.
        Capped at c_rate_cap × capacity and max_power_w.
        """
        if soc >= self.cheap_soc_target or cheap_hours <= 0:
            return 0
        gap_wh   = (self.cheap_soc_target - soc) / 100.0 * self.capacity_wh
        spread_w = gap_wh / cheap_hours
        cap_w    = self.c_rate_cap * self.capacity_wh
        return max(50, min(spread_w, cap_w, self.max_power_w))

    # ── Actuator helpers ─────────────────────────────────────────────────────

    def _set_grid_setpoint(self, watts: float):
        """Switch to NOM strategy and set grid target."""
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
            active_season: str,
            min_price_hour,
            min_price_value,
            soc: float,
            raw_price: float,
            import_price: float,
            soc_target: float,
            soc_floor: float,
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
                "price_discharge": price_discharge,
                "price_charge": price_charge,
                "min_arbitrage_margin": min_arbitrage_margin,
                "prepeak_start": prepeak_start,
                "prepeak_end": prepeak_end,
                "prepeak_window_h": prepeak_window_h,
            },
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

    def _count_cheap_hours(self, price_charge: float) -> int:
        """
        Count consecutive upcoming hours (including the current one) whose raw
        price is below price_charge. Used to spread cheap-window charging.
        Returns at least 1.
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
                if float(prices[key]) < price_charge:
                    count += 1
                else:
                    break
            except (TypeError, ValueError):
                break
            cursor += timedelta(hours=1)
        return max(count, 1)

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
