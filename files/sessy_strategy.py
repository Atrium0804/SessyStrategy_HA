"""
Sessy Charging Strategy — AppDaemon app
Runs every 5 minutes and sets the optimal battery setpoint.

All tunables and entity IDs are configured in apps.yaml (see README) and read
in initialize(); the literals below are only fallback defaults.

Strategy (priority order, each rule individually switchable from the GUI):
  0. Grid-connection guard: every setpoint is clamped to max_grid_w * grid_utilization
  1. Price-spike discharge (price > price_discharge): battery setpoint, discharge toward SOC floor
  2. Cheap/negative price (price < price_charge): battery setpoint, charge toward ceiling
  3. Afternoon charge, SOC < target_afternoon_charging, and the evening peak price
     beats the current price by afternoon_margin: battery setpoint, charge at max power.
     Peak-shaving (avoid net import at the evening peak), not grid trading.
  4. Evening peak sell-off, SOC > target_peak_discharge, no spike remaining and evening
     beats tomorrow's morning peak: grid setpoint export
  5. Morning sell-off, SOC > target_morning_soc: grid setpoint export spread over the window
  6. Default: grid setpoint = 0W (absorb solar, block export)
"""

import appdaemon.plugins.hass.hassapi as hass
from datetime import timedelta


class SessyStrategy(hass.Hass):
    # Brief explanations for each rule/branch, keyed by active_branch name
    _RULE_EXPLANATIONS = {
        # Priority chain rules
        "discharge": "Price-spike discharge: sell battery at high prices, discharge toward SOC floor",
        "cheap_charge": "Cheap charge: buy energy at low/negative prices, charge toward ceiling",
        "cheap_charge_full": "Cheap charge: already at ceiling, holding",
        "afternoon_charge": "Afternoon charge: peak-shaving, charge at max power for evening peak",
        "afternoon_full": "Afternoon charge: already at target SOC, holding",
        "afternoon_skip": "Afternoon charge: skipped, evening peak not high enough vs current price",
        "evening_peak_selloff": "Evening peak sell-off: export excess SOC during peak, spread over window",
        "morning_selloff": "Morning sell-off: export excess SOC during morning window",
        "default": "Default: grid setpoint 0W, absorb solar and block export",
        # Manual and stand-down modes
        "manual_grid": "Manual mode: user-defined grid setpoint",
        "manual_battery": "Manual mode: user-defined battery setpoint",
        "idle": "Idle mode: battery parked, no action",
        "sessy_dynamic": "Sessy dynamic: handed control to Sessy's own schedule",
        "eco": "Eco mode: handed control to Sessy's eco strategy",
    }

    def initialize(self):
        # ── Tunables (overridable from apps.yaml) ───────────────────────────
        self.capacity_wh          = float(self.args.get("capacity_wh", 5000))
        self.max_power_w          = float(self.args.get("max_power_w", 2200))
        # Per-rule SOC targets.
        self.target_afternoon_charging = float(self.args.get("target_afternoon_charging", 90))
        self.target_peak_discharge   = float(self.args.get("target_peak_discharge", 90))
        self.target_morning_soc      = float(self.args.get("target_morning_soc", 30))
        self.soc_floor            = float(self.args.get("soc_floor", 20))
        self.cheap_soc_target     = float(self.args.get("cheap_soc_target", 100))
        self.price_discharge      = float(self.args.get("price_discharge", 0.39))
        self.price_charge         = float(self.args.get("price_charge", -0.10))
        self.afternoon_start      = int(self.args.get("afternoon_start", 15))
        self.afternoon_end        = int(self.args.get("afternoon_end", 17))
        self.afternoon_window_h   = float(self.args.get("afternoon_window_h", 2.0))
        # Adaptive spread window: charge/discharge is spread over the contiguous run
        # of hours the price stays past the threshold, floored at min_window_h.
        # Wider spread = lower power = lower round-trip losses.
        self.min_window_h         = float(self.args.get("min_window_h", 0.5))
        # Seconds to wait after a live input changes before re-running, so a slider
        # drag coalesces into a single run instead of one per intermediate value.
        self.rerun_debounce_s     = float(self.args.get("rerun_debounce_s", 2.0))
        self.evening_peak_start   = int(self.args.get("evening_peak_start", 18))
        self.evening_peak_end     = int(self.args.get("evening_peak_end", 23))
        self.morning_selloff_start = int(self.args.get("morning_selloff_start", 7))
        self.morning_selloff_end   = int(self.args.get("morning_selloff_end", 9))
        self.min_arbitrage_margin = float(self.args.get("min_arbitrage_margin", 0.05))
        # Afternoon-charge break-even: min €/kWh by which the evening peak buy price
        # must exceed the current buy price before topping up for peak-shaving.
        self.afternoon_margin     = float(self.args.get("afternoon_margin", 0.05))
        # Grid-connection guard: clamp every setpoint so grid power stays within
        # max_grid_w * grid_utilization (both import and export).
        self.max_grid_w           = float(self.args.get("max_grid_w", 8000))
        self.grid_utilization     = float(self.args.get("grid_utilization", 0.9))
        self.grid_power_sensor    = self.args.get("grid_power_sensor")

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
        self.target_afternoon_charging_entity = self.args.get("target_afternoon_charging_entity")
        self.target_peak_discharge_entity   = self.args.get("target_peak_discharge_entity")
        self.target_morning_soc_entity      = self.args.get("target_morning_soc_entity")
        self.soc_floor_entity            = self.args.get("soc_floor_entity")
        self.price_discharge_entity      = self.args.get("price_discharge_entity")
        self.price_charge_entity         = self.args.get("price_charge_entity")
        self.min_arbitrage_margin_entity = self.args.get("min_arbitrage_margin_entity")
        self.afternoon_margin_entity     = self.args.get("afternoon_margin_entity")
        self.cheap_soc_target_entity     = self.args.get("cheap_soc_target_entity")
        # Optional per-rule enable switches. When unset, a rule is always enabled.
        self.rule_price_spike_entity     = self.args.get("rule_price_spike_entity")
        self.rule_cheap_charge_entity    = self.args.get("rule_cheap_charge_entity")
        self.rule_afternoon_charge_entity = self.args.get("rule_afternoon_charge_entity")
        self.rule_evening_peak_entity    = self.args.get("rule_evening_peak_entity")
        self.rule_morning_selloff_entity = self.args.get("rule_morning_selloff_entity")

        self._rerun_timer = None

        self.log("Sessy strategy starting up")
        # Delay initial run by 30 seconds to allow Home Assistant to fully initialize
        # This helps avoid race conditions where entities might not be ready immediately
        self.run_in(self.update_strategy, 30)
        # Then run every 5 minutes
        self.run_every(self.update_strategy, self.datetime() + timedelta(seconds=30), 5 * 60)

        # Re-run immediately when the user changes any live input, so tweaks take
        # effect without waiting for the next 5-minute cycle. None entries (unset
        # optional entities) are skipped.
        live_inputs = [
            self.mode_select,
            self.setpoint_entity,
            self.target_afternoon_charging_entity,
            self.target_peak_discharge_entity,
            self.target_morning_soc_entity,
            self.soc_floor_entity,
            self.cheap_soc_target_entity,
            self.price_discharge_entity,
            self.price_charge_entity,
            self.min_arbitrage_margin_entity,
            self.afternoon_margin_entity,
            self.rule_price_spike_entity,
            self.rule_cheap_charge_entity,
            self.rule_afternoon_charge_entity,
            self.rule_evening_peak_entity,
            self.rule_morning_selloff_entity,
        ]
        for entity in live_inputs:
            if entity:
                self.listen_state(self._on_input_change, entity)

    # ── Main logic ────────────────────────────────────────────────────────────

    def update_strategy(self, kwargs):
        # Check if critical entities are available
        if not self._entity_exists(self.soc_sensor) or \
                not self._entity_exists(self.price_sensor):
            self.log("Critical entities (SOC or price sensor) not available — skipping this cycle", level="WARNING")
            return

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
        now_hour   = self.datetime().hour
        soc        = self._get_soc()
        price      = self._current_price()

        if soc is None or price is None:
            self.log("Could not read SOC or price — skipping this cycle", level="WARNING")
            return

        self.log(
            f"Hour={now_hour:02d}  SOC={soc:.0f}%  Price={price:.5f}"
        )

        # Resolve live-tunable values (helper overrides, else apps.yaml default)
        target_afternoon_charging = self._tunable(self.target_afternoon_charging, self.target_afternoon_charging_entity)
        target_peak_discharge   = self._tunable(self.target_peak_discharge, self.target_peak_discharge_entity)
        target_morning_soc      = self._tunable(self.target_morning_soc, self.target_morning_soc_entity)
        soc_floor            = self._tunable(self.soc_floor, self.soc_floor_entity)
        cheap_soc_target     = self._tunable(self.cheap_soc_target, self.cheap_soc_target_entity)
        price_discharge      = self._tunable(self.price_discharge, self.price_discharge_entity)
        price_charge         = self._tunable(self.price_charge, self.price_charge_entity)
        min_arbitrage_margin = self._tunable(self.min_arbitrage_margin, self.min_arbitrage_margin_entity)
        afternoon_margin     = self._tunable(self.afternoon_margin, self.afternoon_margin_entity)
        afternoon_start = self.afternoon_start
        afternoon_end   = self.afternoon_end

        # Common status fields; the decided branch is attached at each return.
        status_fields = dict(
            soc=soc,
            price=price,
            target_afternoon_charging=target_afternoon_charging,
            target_peak_discharge=target_peak_discharge,
            target_morning_soc=target_morning_soc,
            soc_floor=soc_floor,
            cheap_soc_target=cheap_soc_target,
            price_discharge=price_discharge,
            price_charge=price_charge,
            min_arbitrage_margin=min_arbitrage_margin,
            afternoon_margin=afternoon_margin,
            afternoon_start=afternoon_start,
            afternoon_end=afternoon_end,
        )

        # ── Priority 1: price-spike discharge (sell price) ──────────────────
        if self._rule_enabled(self.rule_price_spike_entity) and price > price_discharge:
            window_h    = self._spread_window_h(price_discharge, above=True)
            discharge_w = self._discharge_setpoint(soc, soc_floor, window_h)
            self.log(
                f"DISCHARGE: price {price:.3f} > {price_discharge:.2f} — "
                f"battery setpoint {discharge_w:.0f}W (SOC {soc:.0f}% → floor {soc_floor:.0f}% "
                f"over {window_h:.2f}h)"
            )
            self._publish_status("discharge", **status_fields)
            self._set_battery_setpoint(discharge_w)
            return

        # ── Priority 2: very cheap / negative buy price → charge to ceiling ──
        if self._rule_enabled(self.rule_cheap_charge_entity) and price < price_charge:
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
                f"CHEAP CHARGE: price {price:.5f} < {price_charge} — "
                f"battery setpoint -{charge_w:.0f}W (SOC {soc:.0f}% → {cheap_soc_target:.0f}%)"
            )
            self._publish_status("cheap_charge", **status_fields)
            self._set_battery_setpoint(-charge_w)
            return

        # ── Priority 3: afternoon charge window ──────────────────────────────
        # Peak-shaving, not trading: top up cheaply in the afternoon so the
        # battery — not the grid — covers the evening peak load.
        if self._rule_enabled(self.rule_afternoon_charge_entity) and afternoon_start <= now_hour < afternoon_end:
            if soc >= target_afternoon_charging:
                self.log(
                    f"AFTERNOON: SOC {soc:.0f}% already at target {target_afternoon_charging:.0f}% — "
                    f"holding grid setpoint 0W"
                )
                self._publish_status("afternoon_full", **status_fields)
                self._set_grid_setpoint(0)
                return

            # Break-even guard: only top up if the evening peak price is at least
            # afternoon_margin per kWh above the current price.
            evening_peak_price = self._max_price_in_window(
                self.evening_peak_start, self.evening_peak_end)
            if evening_peak_price is not None and \
                    (evening_peak_price - price) < afternoon_margin:
                self.log(
                    f"AFTERNOON SKIP: evening peak {evening_peak_price:.3f} vs current "
                    f"{price:.3f} (spread < margin {afternoon_margin}) — "
                    f"holding grid setpoint 0W"
                )
                self._publish_status("afternoon_skip", **status_fields)
                self._set_grid_setpoint(0)
                return

            charge_w = self.max_power_w  # charge at full power until target is reached
            self.log(
                f"AFTERNOON CHARGE: battery setpoint -{charge_w:.0f}W "
                f"(SOC {soc:.0f}% → target {target_afternoon_charging:.0f}%)"
            )
            self._publish_status("afternoon_charge", **status_fields)
            self._set_battery_setpoint(-charge_w)   # negative = charge
            return

        # ── Priority 4: evening peak sell-off discharge ────────────────────────
        if self._rule_enabled(self.rule_evening_peak_entity) and \
                self.evening_peak_start <= now_hour < self.evening_peak_end and soc > target_peak_discharge:
            max_remaining_price = self._max_price_in_window(now_hour, 24)
            no_spike_remaining = (max_remaining_price is None or max_remaining_price < price_discharge)
            # Hold for the morning if tomorrow's morning peak price is clearly
            # better than selling now; otherwise sell the excess this evening.
            morning_peak = self._max_price_in_hour_range_tomorrow(
                self.morning_selloff_start, self.morning_selloff_end)
            evening_beats_morning = (morning_peak is None) or \
                (price >= morning_peak - min_arbitrage_margin)
            if no_spike_remaining and evening_beats_morning:
                now_dt = self.datetime()
                peak_end_minutes = self.evening_peak_end * 60
                now_minutes = now_dt.hour * 60 + now_dt.minute
                hours_remaining = (peak_end_minutes - now_minutes) / 60
                discharge_w = self._excess_setpoint(soc, target_peak_discharge, hours_remaining)
                # Grid setpoint (negative = export) so the battery covers household
                # load AND the export target. A high home load makes the battery
                # work harder instead of pulling the shortfall from the grid.
                self.log(
                    f"EVENING PEAK SELL-OFF: SOC {soc:.0f}% > target {target_peak_discharge:.0f}% — "
                    f"grid export setpoint -{discharge_w:.0f}W "
                    f"(spread over {hours_remaining:.2f}h remaining peak window)"
                )
                self._publish_status("evening_peak_selloff", **status_fields)
                self._set_grid_setpoint(-discharge_w)
                return

        # ── Priority 5: morning sell-off ─────────────────────────────────────
        if self._rule_enabled(self.rule_morning_selloff_entity) and \
                self.morning_selloff_start <= now_hour < self.morning_selloff_end and soc > target_morning_soc:
            now_dt = self.datetime()
            end_minutes = self.morning_selloff_end * 60
            now_minutes = now_dt.hour * 60 + now_dt.minute
            hours_remaining = (end_minutes - now_minutes) / 60
            discharge_w = self._excess_setpoint(soc, target_morning_soc, hours_remaining)
            self.log(
                f"MORNING SELL-OFF: SOC {soc:.0f}% > target {target_morning_soc:.0f}% — "
                f"grid export setpoint -{discharge_w:.0f}W "
                f"(spread over {hours_remaining:.2f}h remaining morning window)"
            )
            self._publish_status("morning_selloff", **status_fields)
            self._set_grid_setpoint(-discharge_w)
            return

        # ── Priority 6: default — grid setpoint 0W (solar absorption) ────────
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
        if not self._entity_exists(self.strategy_select):
            self.log("Strategy select entity not available", level="WARNING")
            self._publish_branch(branch, sessy_strategy=strategy_option)
            return

        try:
            current = self.get_state(self.strategy_select)
            if current != strategy_option:
                self.call_service(
                    "select/select_option",
                    entity_id=self.strategy_select,
                    option=strategy_option,
                )
                self.log(f"Strategy → {strategy_option} ({branch})")
            self._publish_branch(branch, sessy_strategy=strategy_option)
        except Exception as e:
            self.log(f"Failed to apply standby strategy: {e}", level="WARNING")
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

    def _rule_enabled(self, entity_id) -> bool:
        """
        Whether a priority rule is enabled. Rules without a configured switch are
        always on; an unreadable switch also defaults to on (fail-safe).
        """
        if not entity_id:
            return True
        try:
            state = self.get_state(entity_id)
        except Exception:
            return True
        if state is None:
            return True
        return str(state).strip().lower() in ("on", "true", "yes", "enabled", "1")

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
        Always charges at max_power_w when below cheap_soc_target.
        """
        if soc >= cheap_soc_target:
            return 0
        return self.max_power_w

    def _excess_setpoint(self, soc: float, target: float, hours_remaining: float) -> float:
        """
        Watts of excess SOC above target to sell, spread over the remaining
        window. Applied as a negative grid setpoint (negative = export), so the
        battery covers household load on top of the export and never imports to
        top up. Minimum 500W; clamped at max_power_w.
        """
        gap_wh   = (soc - target) / 100.0 * self.capacity_wh
        if gap_wh <= 0:
            return 0
        spread_w = gap_wh / max(hours_remaining, 0.083)  # avoid div/0
        return max(500, min(spread_w, self.max_power_w))

    # ── Actuator helpers ─────────────────────────────────────────────────────

    def _grid_limit_w(self) -> float:
        """Allowed grid power in W: connection limit × utilisation margin."""
        return self.max_grid_w * self.grid_utilization

    def _clamp_to_grid_limit(self, watts: float, kind: str) -> float:
        """
        Grid-connection guard: keep any commanded setpoint within the allowed
        grid power. For grid (nom) setpoints the limit applies directly; for
        battery (api) setpoints it is combined with the inverter's max power.
        """
        limit = self._grid_limit_w()
        if kind == "battery":
            limit = min(limit, self.max_power_w)
        clamped = max(-limit, min(watts, limit))
        if abs(clamped - watts) > 1:
            self.log(
                f"Grid guard: clamped {kind} setpoint {watts:.0f}W → {clamped:.0f}W "
                f"(limit ±{limit:.0f}W)"
            )
        return clamped

    def _set_grid_setpoint(self, watts: float):
        """Switch to NOM strategy and set grid target (positive = import, negative = export)."""
        if not self._entity_exists(self.strategy_select) or not self._entity_exists(self.grid_target):
            self.log("Grid setpoint entities not available", level="WARNING")
            return

        watts = self._clamp_to_grid_limit(watts, "grid")
        try:
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
        except Exception as e:
            self.log(f"Failed to set grid setpoint: {e}", level="WARNING")

    def _set_battery_setpoint(self, watts: float):
        """
        Switch to API strategy and set battery power setpoint.
        Positive = discharge, negative = charge.
        """
        if not self._entity_exists(self.strategy_select) or not self._entity_exists(self.battery_setpoint):
            self.log("Battery setpoint entities not available", level="WARNING")
            return

        watts = self._clamp_to_grid_limit(watts, "battery")
        try:
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
        except Exception as e:
            self.log(f"Failed to set battery setpoint: {e}", level="WARNING")

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

    def _entity_exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists and is available in Home Assistant.
        Returns False if the entity doesn't exist or its state cannot be read.
        """
        if not entity_id:
            return False
        try:
            state = self.get_state(entity_id)
            return state is not None
        except Exception:
            return False

    def _publish_status(self, active_branch: str, **fields):
        """
        Publish the strategy status sensor: state = active branch, attributes =
        every field the decided branch passed in.
        """
        if not self.status_sensor or not self._entity_exists(self.status_sensor):
            return

        attributes = {"active_branch": active_branch}
        attributes.update(fields)
        # Add rule explanation
        attributes["rule_explanation"] = self._RULE_EXPLANATIONS.get(active_branch, "Unknown rule")

        try:
            self.set_state(
                self.status_sensor,
                state=active_branch,
                attributes=attributes,
            )
        except Exception as e:
            self.log(f"Failed to publish status: {e}", level="WARNING")

    def _publish_branch(self, active_branch: str, **extra):
        """
        Lightweight status publish for manual and stand-down modes, where the
        full optimisation context (thresholds) does not apply. Sets the status
        state to the active branch and records any extra fields.
        """
        if not self.status_sensor or not self._entity_exists(self.status_sensor):
            return
        try:
            attributes = {"active_branch": active_branch, **extra}
            # Add rule explanation
            attributes["rule_explanation"] = self._RULE_EXPLANATIONS.get(active_branch, "Unknown rule")
            self.set_state(
                self.status_sensor,
                state=active_branch,
                attributes=attributes,
            )
        except Exception as e:
            self.log(f"Failed to publish branch status: {e}", level="WARNING")

    def _get_soc(self) -> float | None:
        state = self.get_state(self.soc_sensor)
        try:
            return float(state)
        except (TypeError, ValueError):
            return None

    def _current_price(self) -> float | None:
        """
        Read the current hour's price from the energy_prices attribute, falling
        back to the sensor state.
        """
        try:
            prices = self.get_state(self.price_sensor, attribute="energy_prices")
            value = None
            if prices:
                now_key = self.datetime().strftime("%Y-%m-%dT%H:00:00")
                if now_key in prices:
                    value = float(prices[now_key])
            if value is None:
                value = float(self.get_state(self.price_sensor))
            return value
        except (TypeError, ValueError, KeyError):
            return None

    def _get_prices_dict(self):
        """Return the energy_prices dict, or None if unavailable."""
        try:
            prices = self.get_state(self.price_sensor, attribute="energy_prices")
        except (TypeError, ValueError):
            return None
        if not prices:
            return None
        return prices

    def _contiguous_price_hours(self, threshold: float, above: bool) -> int:
        """
        Count consecutive upcoming hours (including the current one) whose price
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
        Return the maximum price across today's [start_hour, end_hour) slots,
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

    def _max_price_in_hour_range_tomorrow(self, start_hour: int, end_hour: int) -> float | None:
        """
        Return the maximum price across tomorrow's [start_hour, end_hour) slots,
        or None if tomorrow's prices are not yet available.
        """
        prices = self._get_prices_dict()
        if not prices:
            return None
        tomorrow = (self.datetime() + timedelta(days=1)).strftime("%Y-%m-%d")
        values = []
        for hour in range(start_hour, end_hour):
            key = f"{tomorrow}T{hour:02d}:00:00"
            if key in prices:
                try:
                    values.append(float(prices[key]))
                except (TypeError, ValueError):
                    continue
        return max(values) if values else None
