"""
Boiler Charging Strategy — AppDaemon app
Runs every 15 minutes and picks the boiler mode from a user-selected strategy
mode plus weekly legionella prevention.

All tunables and entity IDs are configured in apps.yaml (see README) and read
in initialize(); the literals below are only fallback defaults.

Strategy (priority order):
  1. Legionella boost (temp hasn't reached legionella_temp in legionella_boost_days):
     force mode 'boost' at legionella_temp — always, regardless of price period —
     unless the user has explicitly selected mode 'off'.
  2. Legionella warning (temp hasn't reached legionella_temp in legionella_hybrid_days):
     force mode 'hybrid' at the normal setpoint, but only during the cheapest of
     the two configured day/night periods; outside that period, dispatch falls
     through to the regular user mode selection (step 3) instead.
  3. User mode dispatch (mode_select):
       off / heatpump / hybrid / boost -> force that boiler mode directly.
       economic (default)        -> run the heat pump only during whichever of
                                     the two configured day/night periods (e.g. 10:00-16:00
                                     vs 00:00-06:00) has the lower average price;
                                     stay off outside that period.

The setpoint is held fixed at setpoint_c except during a legionella boost.
"""

import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta

# Human-readable label per active_branch value, exposed as the
# 'active_branch_label' attribute on the status sensor.
BRANCH_LABELS = {
    "legionella_boost": "Legionella Boost",
    "legionella_hybrid": "Legionella Hybrid",
    "force_off": "Forced Off",
    "force_heatpump": "Forced Heat Pump",
    "force_hybrid": "Forced Hybrid",
    "force_boost": "Forced Boost",
    "economic_heatpump": "Economic Heat Pump",
    "economic_off": "Economic Off",
}


class BoilerStrategy(hass.Hass):

    def initialize(self):
        # ── Tunables (overridable from apps.yaml) ───────────────────────────
        self.setpoint_c = float(self.args.get("setpoint_c", 60))

        # ── Weekly legionella prevention ─────────────────────────────────────
        self.legionella_temp        = float(self.args.get("legionella_temp", 65))
        self.legionella_hybrid_days = float(self.args.get("legionella_hybrid_days", 6))
        self.legionella_boost_days  = float(self.args.get("legionella_boost_days", 7))

        # ── Economic mode day/night periods (local hours, [start, end)) ─────────
        # 'economic' compares the average forecast price of these two periods and
        # runs the heat pump only during whichever period is cheaper.
        self.eco_day_start = int(self.args.get("economic_day_start", 10))
        self.eco_day_end   = int(self.args.get("economic_day_end", 16))
        self.eco_night_start = int(self.args.get("economic_night_start", 0))
        self.eco_night_end   = int(self.args.get("economic_night_end", 6))

        # Seconds to wait after a live input changes before re-running, so a
        # slider drag coalesces into a single run instead of one per intermediate value.
        self.rerun_debounce_s = float(self.args.get("rerun_debounce_s", 2.0))

        # ── Entity IDs (overridable from apps.yaml) ─────────────────────────
        self.temp_sensor              = self.args.get("temp_sensor",              "sensor.boiler_temperatuur")
        self.price_forecast_sensor    = self.args.get("price_forecast_sensor",    "sensor.frankenergy_current_electricity_market_price")
        self.price_forecast_attribute = self.args.get("price_forecast_attribute", "prices")
        self.mode_select              = self.args.get("mode_select",              "input_select.boiler_strategy_mode")
        self.boiler_mode_select       = self.args.get("boiler_mode_select",       "select.boiler_mode")
        self.boiler_setpoint_entity   = self.args.get("boiler_setpoint_entity",   "number.boiler_setpoint")
        self.legionella_last_ok_entity = self.args.get("legionella_last_ok_entity", "input_datetime.boiler_legionella_last_ok")
        self.status_sensor            = self.args.get("status_sensor",            "sensor.boiler_strategy_status")

        self._rerun_timer = None

        self.log("Boiler strategy starting up")
        self.run_in(self.update_strategy, 30)
        self.run_every(self.update_strategy, self.datetime() + timedelta(seconds=30), 15 * 60)

        live_inputs = [
            self.temp_sensor,
            self.price_forecast_sensor,
            self.mode_select,
        ]
        for entity in live_inputs:
            if entity:
                self.listen_state(self._on_input_change, entity)

    # ── Main logic ────────────────────────────────────────────────────────────

    def update_strategy(self, kwargs):
        temp = self._get_temp()
        if temp is None:
            self.log("Could not read boiler temperature — skipping this cycle", level="WARNING")
            return

        self._record_legionella_ok_if_reached(temp)
        days_since_ok = self._days_since_legionella_ok()
        mode = self._get_mode()

        status_fields = dict(
            temp=temp,
            mode=mode,
            days_since_legionella_ok=days_since_ok,
        )

        # ── Priority 1: legionella boost deadline — always, unless user forced 'off' ──
        if days_since_ok >= self.legionella_boost_days and mode != "off":
            self.log(
                f"LEGIONELLA BOOST: {days_since_ok:.1f} days since last reaching "
                f"{self.legionella_temp:.0f}C — forcing boost to {self.legionella_temp:.0f}C"
            )
            self._publish_status("legionella_boost", **status_fields)
            self._set_boiler_mode("boost")
            self._set_boiler_setpoint(self.legionella_temp)
            return

        # ── Priority 2: legionella warning — escalate to hybrid during cheapest period only ──
        if days_since_ok >= self.legionella_hybrid_days:
            prices = self._get_prices()
            now_hour = self.datetime().hour
            in_window, day_avg_price, night_avg_price, cheapest_period = self._cheapest_window_info(now_hour, prices)
            if in_window:
                self.log(
                    f"LEGIONELLA WARNING: {days_since_ok:.1f} days since last reaching "
                    f"{self.legionella_temp:.0f}C — cheapest={cheapest_period} — forcing hybrid at {self.setpoint_c:.0f}C"
                )
                self._publish_status(
                    "legionella_hybrid",
                    day_avg_price=day_avg_price,
                    night_avg_price=night_avg_price,
                    cheapest_period=cheapest_period,
                    **status_fields,
                )
                self._set_boiler_mode("hybrid")
                self._set_boiler_setpoint(self.setpoint_c)
                return
            # Outside the cheap period — fall through to the regular user mode dispatch.

        # ── Priority 3a: forced user mode ────────────────────────────────────
        if mode in ("off", "heatpump", "hybrid", "boost"):
            self.log(f"FORCE MODE: user selected '{mode}'")
            self._publish_status(f"force_{mode}", **status_fields)
            self._set_boiler_mode(mode)
            self._set_boiler_setpoint(self.setpoint_c)
            return

        # ── Priority 3b: economic — heat pump during the cheaper period ───────
        prices = self._get_prices()
        now_hour = self.datetime().hour
        boiler_mode, day_avg_price, night_avg_price, cheapest_period = self._economic_decision(now_hour, prices)
        self.log(
            f"ECONOMIC: hour={now_hour} day_avg_price={day_avg_price} night_avg_price={night_avg_price} "
            f"cheapest={cheapest_period} — mode={boiler_mode}"
        )
        self._publish_status(
            f"economic_{boiler_mode}",
            day_avg_price=day_avg_price, night_avg_price=night_avg_price, cheapest_period=cheapest_period,
            **status_fields,
        )
        self._set_boiler_mode(boiler_mode)
        self._set_boiler_setpoint(self.setpoint_c)

    # ── Economic-mode decision ───────────────────────────────────────────────

    def _cheapest_window_info(self, now_hour, prices):
        """
        Pick the cheaper of the two configured day/night periods by average forecast price.
        Returns (in_window, day_avg_price, night_avg_price, cheapest_period), where
        in_window is True when now_hour falls inside the cheapest period. If no
        forecast is available, in_window is False (nothing is known to be cheap yet).
        """
        day_window = (self.eco_day_start, self.eco_day_end)
        night_window = (self.eco_night_start, self.eco_night_end)
        day_avg_price = self._window_average(prices, *day_window)
        night_avg_price = self._window_average(prices, *night_window)

        candidates = []
        if day_avg_price is not None:
            candidates.append((day_avg_price, day_window, "day"))
        if night_avg_price is not None:
            candidates.append((night_avg_price, night_window, "night"))
        if not candidates:
            return False, day_avg_price, night_avg_price, None

        _, (start_h, end_h), cheapest_period = min(candidates, key=lambda c: c[0])
        in_window = start_h <= now_hour < end_h
        return in_window, day_avg_price, night_avg_price, cheapest_period

    def _economic_decision(self, now_hour, prices):
        """
        Return 'heatpump' if now falls inside the cheapest configured period, else 'off'.
        Returns (boiler_mode, day_avg_price, night_avg_price, cheapest_period).
        """
        in_window, day_avg_price, night_avg_price, cheapest_period = self._cheapest_window_info(now_hour, prices)
        return ("heatpump" if in_window else "off"), day_avg_price, night_avg_price, cheapest_period

    def _window_average(self, prices, start_h, end_h):
        """Average forecast price over entries whose start hour is in [start_h, end_h)."""
        price_values = []
        for entry in prices or []:
            hour = self._entry_hour(entry)
            if hour is None or not (start_h <= hour < end_h):
                continue
            try:
                price_values.append(float(entry.get("price")))
            except (TypeError, ValueError, AttributeError):
                continue
        if not price_values:
            return None
        return sum(price_values) / len(price_values)

    @staticmethod
    def _entry_hour(entry):
        if not isinstance(entry, dict):
            return None
        raw = entry.get("from")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw)).hour
        except ValueError:
            return None


    # ── Legionella tracking ──────────────────────────────────────────────────

    def _record_legionella_ok_if_reached(self, temp: float):
        """Stamp legionella_last_ok_entity with now whenever the boiler reaches legionella_temp."""
        if temp < self.legionella_temp:
            return
        if not self.legionella_last_ok_entity:
            return
        try:
            self.call_service(
                "input_datetime/set_datetime",
                entity_id=self.legionella_last_ok_entity,
                datetime=self.datetime().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            self.log(f"Failed to stamp legionella_last_ok: {e}", level="WARNING")

    def _days_since_legionella_ok(self) -> float:
        """
        Days since the boiler last reached legionella_temp. If the tracking
        helper has never been set, treat it as already at the hybrid warning
        threshold — escalates to hybrid but stops short of forcing a boost
        on a fresh install.
        """
        if not self.legionella_last_ok_entity:
            return self.legionella_hybrid_days
        state = self.get_state(self.legionella_last_ok_entity)
        if not state or state in ("unknown", "unavailable"):
            self.log("legionella_last_ok has no value yet — assuming hybrid warning", level="WARNING")
            return self.legionella_hybrid_days
        try:
            last_ok = datetime.strptime(state, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self.log(f"Could not parse legionella_last_ok state '{state}'", level="WARNING")
            return self.legionella_hybrid_days
        return (self.datetime() - last_ok).total_seconds() / 86400.0

    # ── Live-input re-run ────────────────────────────────────────────────────

    def _on_input_change(self, entity, attribute, old, new, kwargs):
        if old == new:
            return
        if self._rerun_timer is not None:
            self.cancel_timer(self._rerun_timer)
        self.log(f"Input {entity} changed {old} → {new} — re-running in {self.rerun_debounce_s:.0f}s")
        self._rerun_timer = self.run_in(self._rerun_now, self.rerun_debounce_s)

    def _rerun_now(self, kwargs):
        self._rerun_timer = None
        self.update_strategy({})

    # ── Actuator helpers ──────────────────────────────────────────────────────

    def _set_boiler_mode(self, option: str):
        if not self._entity_exists(self.boiler_mode_select):
            self.log("Boiler mode select entity not available", level="WARNING")
            return
        try:
            current = self.get_state(self.boiler_mode_select)
            if current != option:
                self.call_service(
                    "select/select_option",
                    entity_id=self.boiler_mode_select,
                    option=option,
                )
                self.log(f"Boiler mode → {option}")
        except Exception as e:
            self.log(f"Failed to set boiler mode: {e}", level="WARNING")

    def _set_boiler_setpoint(self, celsius: float):
        if not self._entity_exists(self.boiler_setpoint_entity):
            self.log("Boiler setpoint entity not available", level="WARNING")
            return
        try:
            current = self.get_state(self.boiler_setpoint_entity)
            if current is None or float(current) != celsius:
                self.call_service(
                    "number/set_value",
                    entity_id=self.boiler_setpoint_entity,
                    value=celsius,
                )
                self.log(f"Boiler setpoint → {celsius:.0f}C")
        except (TypeError, ValueError) as e:
            self.log(f"Failed to set boiler setpoint: {e}", level="WARNING")

    # ── Sensor readers ────────────────────────────────────────────────────────

    def _get_mode(self) -> str:
        """User-selected strategy mode; defaults to 'economic' when unset."""
        if not self.mode_select:
            return "economic"
        raw = self.get_state(self.mode_select)
        if raw in (None, "unknown", "unavailable", ""):
            return "economic"
        return str(raw).strip().lower()

    def _get_prices(self):
        """Hourly forecast list ([{from, till, price}, ...]) or None."""
        if not self.price_forecast_sensor:
            return None
        try:
            return self.get_state(self.price_forecast_sensor, attribute=self.price_forecast_attribute)
        except Exception:
            return None

    def _get_temp(self) -> float | None:
        try:
            return float(self.get_state(self.temp_sensor))
        except (TypeError, ValueError):
            return None

    def _entity_exists(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        try:
            return self.get_state(entity_id) is not None
        except Exception:
            return False

    def _publish_status(self, active_branch: str, **fields):
        if not self.status_sensor or not self._entity_exists(self.status_sensor):
            return
        try:
            self.set_state(
                self.status_sensor,
                state=active_branch,
                attributes={
                    "active_branch": active_branch,
                    "active_branch_label": BRANCH_LABELS.get(active_branch, active_branch),
                    **fields,
                },
            )
        except Exception as e:
            self.log(f"Failed to publish status: {e}", level="WARNING")
