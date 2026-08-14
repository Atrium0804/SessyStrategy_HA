"""
Boiler Charging Strategy — AppDaemon app
Runs every 15 minutes and picks the optimal boiler mode based on dynamic
energy prices, battery SOC, and weekly legionella prevention.

All tunables and entity IDs are configured in apps.yaml (see README) and read
in initialize(); the literals below are only fallback defaults.

Strategy (priority order):
  1. Legionella boost (temp hasn't reached legionella_temp in legionella_boost_days):
     force mode 'boost' and temporarily raise the setpoint to legionella_temp.
  2. Legionella warning (temp hasn't reached legionella_temp in legionella_hybrid_days):
     force mode 'hybrid' at the normal setpoint, giving the resistance a head
     start before the hard boost deadline hits.
  3. Price/SOC optimisation: compare the relevant price (import price if the
     battery isn't full, export price if it is) against a gas-equivalent
     price to decide 'off' / 'heatpump' / 'hybrid'.

The setpoint is held fixed at setpoint_c except during a legionella boost.
"""

import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta


class BoilerStrategy(hass.Hass):

    def initialize(self):
        # ── Tunables (overridable from apps.yaml) ───────────────────────────
        self.setpoint_c           = float(self.args.get("setpoint_c", 60))
        self.soc_full_threshold   = float(self.args.get("soc_full_threshold", 95))
        self.gas_price            = float(self.args.get("gas_price", 1.50))
        self.boiler_efficiency    = float(self.args.get("boiler_efficiency", 95))
        self.cop                  = float(self.args.get("cop", 2.0))
        self.calorific_value      = float(self.args.get("calorific_value", 9.77))
        self.buy_surcharge        = float(self.args.get("buy_surcharge", 0.025))
        self.energy_tax           = float(self.args.get("energy_tax", 0.0916))
        self.vat                  = float(self.args.get("vat", 1.21))
        self.sell_surcharge       = float(self.args.get("sell_surcharge", 0.025))

        # ── Weekly legionella prevention ─────────────────────────────────────
        self.legionella_temp        = float(self.args.get("legionella_temp", 65))
        self.legionella_hybrid_days = float(self.args.get("legionella_hybrid_days", 6))
        self.legionella_boost_days  = float(self.args.get("legionella_boost_days", 7))

        # Seconds to wait after a live input changes before re-running, so a
        # slider drag coalesces into a single run instead of one per intermediate value.
        self.rerun_debounce_s = float(self.args.get("rerun_debounce_s", 2.0))

        # ── Entity IDs (overridable from apps.yaml) ─────────────────────────
        self.temp_sensor           = self.args.get("temp_sensor",           "sensor.boiler_temperature")
        self.price_sensor          = self.args.get("price_sensor",          "sensor.nordpool_actuele_prijs")
        self.soc_sensor             = self.args.get("soc_sensor",            "sensor.sessy_battery_alt9_state_of_charge")
        self.boiler_mode_select    = self.args.get("boiler_mode_select",    "select.boiler_modus")
        self.boiler_setpoint_entity = self.args.get("boiler_setpoint_entity", "number.boiler_setpoint")
        self.legionella_last_ok_entity = self.args.get("legionella_last_ok_entity", "input_datetime.boiler_legionella_last_ok")
        self.status_sensor         = self.args.get("status_sensor",         "sensor.boiler_strategy_status")

        # Optional live-tuning helpers (input_number). If set, these override the
        # corresponding static default each cycle, so the value can be changed
        # from the HA UI without restarting AppDaemon.
        self.soc_full_threshold_entity = self.args.get("soc_full_threshold_entity")
        self.gas_price_entity          = self.args.get("gas_price_entity")
        self.boiler_efficiency_entity  = self.args.get("boiler_efficiency_entity")
        self.cop_entity                = self.args.get("cop_entity")

        self._rerun_timer = None

        self.log("Boiler strategy starting up")
        self.run_in(self.update_strategy, 30)
        self.run_every(self.update_strategy, self.datetime() + timedelta(seconds=30), 15 * 60)

        live_inputs = [
            self.temp_sensor,
            self.price_sensor,
            self.soc_sensor,
            self.soc_full_threshold_entity,
            self.gas_price_entity,
            self.boiler_efficiency_entity,
            self.cop_entity,
        ]
        for entity in live_inputs:
            if entity:
                self.listen_state(self._on_input_change, entity)

    # ── Main logic ────────────────────────────────────────────────────────────

    def update_strategy(self, kwargs):
        temp  = self._get_temp()
        price = self._get_current_price()
        soc   = self._get_soc()

        if temp is None or price is None or soc is None:
            self.log("Could not read temp, price or SOC — skipping this cycle", level="WARNING")
            return

        self._record_legionella_ok_if_reached(temp)
        days_since_ok = self._days_since_legionella_ok()

        soc_full_threshold = self._tunable(self.soc_full_threshold, self.soc_full_threshold_entity)
        gas_price           = self._tunable(self.gas_price, self.gas_price_entity)
        boiler_efficiency   = self._tunable(self.boiler_efficiency, self.boiler_efficiency_entity)
        cop                 = self._tunable(self.cop, self.cop_entity)

        buy_price, sell_price = self._compute_prices(price)
        status_fields = dict(
            temp=temp,
            raw_price=price,
            buy_price=buy_price,
            sell_price=sell_price,
            soc=soc,
            soc_full_threshold=soc_full_threshold,
            days_since_legionella_ok=days_since_ok,
        )

        # ── Priority 1: legionella boost deadline ────────────────────────────
        if days_since_ok >= self.legionella_boost_days:
            self.log(
                f"LEGIONELLA BOOST: {days_since_ok:.1f} days since last reaching "
                f"{self.legionella_temp:.0f}C — forcing boost to {self.legionella_temp:.0f}C"
            )
            self._publish_status("legionella_boost", **status_fields)
            self._set_boiler_mode("boost")
            self._set_boiler_setpoint(self.legionella_temp)
            return

        # ── Priority 2: legionella warning — escalate to hybrid ──────────────
        if days_since_ok >= self.legionella_hybrid_days:
            self.log(
                f"LEGIONELLA WARNING: {days_since_ok:.1f} days since last reaching "
                f"{self.legionella_temp:.0f}C — forcing hybrid at {self.setpoint_c:.0f}C"
            )
            self._publish_status("legionella_hybrid", **status_fields)
            self._set_boiler_mode("hybrid")
            self._set_boiler_setpoint(self.setpoint_c)
            return

        # ── Priority 3: price/SOC optimisation ───────────────────────────────
        soc_full        = soc >= soc_full_threshold
        relevant_price  = sell_price if soc_full else buy_price
        gas_equiv_price = gas_price / (self.calorific_value * (boiler_efficiency / 100.0))
        threshold_hp    = gas_equiv_price * cop
        threshold_res   = gas_equiv_price
        heatpump_worth_it  = relevant_price <= threshold_hp
        resistance_worth_it = soc_full and relevant_price <= threshold_res

        mode = "hybrid" if resistance_worth_it else ("heatpump" if heatpump_worth_it else "off")
        self.log(
            f"PRICE MODE: soc_full={soc_full} relevant_price={relevant_price:.4f} "
            f"threshold_hp={threshold_hp:.4f} threshold_res={threshold_res:.4f} — mode={mode}"
        )
        self._publish_status(
            f"price_{mode}", gas_equiv_price=gas_equiv_price,
            threshold_hp=threshold_hp, threshold_res=threshold_res, **status_fields,
        )
        self._set_boiler_mode(mode)
        self._set_boiler_setpoint(self.setpoint_c)

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

    # ── Pricing ───────────────────────────────────────────────────────────────

    def _compute_prices(self, raw_price: float) -> tuple[float, float]:
        """Import price (bought when charging from grid) and export price (opportunity cost)."""
        buy_price  = (raw_price + self.buy_surcharge + self.energy_tax) * self.vat
        sell_price = raw_price - self.sell_surcharge
        return buy_price, sell_price

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

    def _tunable(self, default: float, entity_id) -> float:
        if not entity_id:
            return default
        try:
            return float(self.get_state(entity_id))
        except (TypeError, ValueError):
            return default

    def _get_temp(self) -> float | None:
        try:
            return float(self.get_state(self.temp_sensor))
        except (TypeError, ValueError):
            return None

    def _get_current_price(self) -> float | None:
        try:
            return float(self.get_state(self.price_sensor))
        except (TypeError, ValueError):
            return None

    def _get_soc(self) -> float | None:
        try:
            return float(self.get_state(self.soc_sensor))
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
                attributes={"active_branch": active_branch, **fields},
            )
        except Exception as e:
            self.log(f"Failed to publish status: {e}", level="WARNING")
