"""
Boiler Charging Strategy — AppDaemon app
Runs every 15 minutes and picks the boiler mode from a user-selected strategy
mode plus weekly legionella prevention.

All tunables and entity IDs are configured in apps.yaml (see README) and read
in initialize(); the literals below are only fallback defaults.

Strategy (priority order):
  1. Legionella boost (temp hasn't reached legionella_temp in legionella_boost_days):
     force mode 'boost' — always, regardless of price period — unless the user
     has explicitly selected mode 'off'.
  2. User mode dispatch (mode_select):
       off / heatpump / hybrid / boost -> force that boiler mode directly.
       cheapest_hours (default)  -> falls through to legionella warning (3),
                                     then cheapest hours decision (5).
       market_price_threshold   -> falls through to legionella warning (3),
                                     then market price threshold decision (4).
     The retired 'economic' mode (and an unset mode) runs as cheapest_hours.
  3. Legionella warning (temp hasn't reached legionella_temp in legionella_hybrid_days),
     only while mode is 'market_price_threshold' or 'cheapest_hours':
     force mode 'hybrid', but only during the cheapest period for that strategy;
     outside that period, dispatch falls through to the respective price decision.
  4. Market price threshold: run the heat pump whenever the current price
     (from the shared price data, see cheapest_hours.py) is at or below the
     configured threshold (default: 0.1).
  5. Cheapest hours: run the heat pump during the N cheapest hours of the price
     window shared with the battery strategy (cheapest_hours.py; N is
     configurable, default: 1).

The boiler's own max_temp is used as the target whenever a temperature needs
to be pushed (boost, legionella warning); there is no separate user setpoint.
"""

import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta

import cheapest_hours as ch

DEFAULT_MODE = "cheapest_hours"
# Modes that no longer exist; a leftover selection runs as DEFAULT_MODE.
RETIRED_MODES = {"economic"}

# Human-readable label per active_branch value, exposed as the
# 'active_branch_label' attribute on the status sensor.
BRANCH_LABELS = {
    "legionella_boost": "Legionella Boost",
    "legionella_hybrid": "Legionella Hybrid",
    "force_off": "Forced Off",
    "force_heatpump": "Forced Heat Pump",
    "force_hybrid": "Forced Hybrid",
    "force_boost": "Forced Boost",
    "market_price_heatpump": "Market Price Heat Pump",
    "market_price_off": "Market Price Off",
    "cheapest_hours_heatpump": "Cheapest Hours Heat Pump",
    "cheapest_hours_off": "Cheapest Hours Off",
}

# Brief explanations for each rule/branch, exposed as the
# 'rule_explanation' attribute on the status sensor.
RULE_EXPLANATIONS = {
    "legionella_boost": "Legionella Boost: force boost mode when temp hasn't reached target in 7 days",
    "legionella_hybrid": "Legionella Hybrid: force hybrid mode during cheapest period when approaching deadline",
    "force_off": "Forced Off: user manually selected off mode",
    "force_heatpump": "Forced Heat Pump: user manually selected heat pump only mode",
    "force_hybrid": "Forced Hybrid: user manually selected hybrid mode",
    "force_boost": "Forced Boost: user manually selected boost mode",
    "market_price_heatpump":  "Market Price: run heat pump when price is below threshold",
    "market_price_off": "Market Price: keep off when price is above threshold",
    "cheapest_hours_heatpump": "Cheapest Hours: run heat pump during N cheapest hours of the day",
    "cheapest_hours_off": "Cheapest Hours: keep off outside the N cheapest hours",
}


class BoilerStrategy(hass.Hass):

    def initialize(self):
        # ── Weekly legionella prevention settings  ─────────────────────────────────────
        self.legionella_temp        = float(self.args.get("legionella_temp", 65))
        self.legionella_hybrid_days = float(self.args.get("legionella_hybrid_days", 6))
        self.legionella_boost_days  = float(self.args.get("legionella_boost_days", 7))

        # ── Market price threshold strategy ───────────────────────────────────
        # Run heat pump when current market price is below this threshold
        self.market_price_threshold = float(self.args.get("market_price_threshold", 0.1))
        self.market_price_threshold_entity = self.args.get("market_price_threshold_entity", "input_number.boiler_market_price_threshold")

        # ── Cheapest hours strategy ──────────────────────────────────────────
        # Number of cheapest hours to use heat pump (default: 1)
        self.cheapest_hours_count = int(self.args.get("cheapest_hours_count", 1))
        # Shared with the battery strategy: ranking window starts at this hour and
        # spans 24h (default 02:00 to 02:00, ch.DEFAULT_WINDOW_START_H).
        self.cheapest_window_start_h = int(self.args.get("cheapest_window_start_h", ch.DEFAULT_WINDOW_START_H))
        self.cheapest_hours_count_entity = self.args.get("cheapest_hours_count_entity", "input_number.boiler_cheapest_hours_count")

        # Seconds to wait after a live input changes before re-running, so a
        # slider drag coalesces into a single run instead of one per intermediate value.
        self.rerun_debounce_s = float(self.args.get("rerun_debounce_s", 2.0))

        # ── Entity IDs (overridable from apps.yaml) ─────────────────────────
        self.temp_sensor              = self.args.get("temp_sensor",              "sensor.boiler_temperatuur")
        self.price_forecast_sensor    = self.args.get("price_forecast_sensor",    "sensor.sessy_dnhh_energy_price")
        self.price_forecast_attribute = self.args.get("price_forecast_attribute", "energy_prices")
        self.current_price_sensor     = self.args.get("current_price_sensor",     "sensor.current_energy_price")
        self.current_price_attribute = self.args.get("current_price_attribute", "price")
        self.mode_select              = self.args.get("mode_select",              "input_select.boiler_strategy_mode")
        self.boiler_mode_select       = self.args.get("boiler_mode_select",       "select.boiler_mode")
        self.legionella_last_ok_entity = self.args.get("legionella_last_ok_entity", "input_datetime.boiler_legionella_last_ok")
        self.status_sensor            = self.args.get("status_sensor",            "sensor.boiler_strategy_status")

        self._rerun_timer = None

        self.log("Boiler strategy starting up")
        self.run_in(self.update_strategy, 30)
        self.run_every(self.update_strategy, self.datetime() + timedelta(seconds=30), 15 * 60)

        live_inputs = [
            self.temp_sensor,
            self.price_forecast_sensor,
            self.current_price_sensor,
            self.mode_select,
            self.market_price_threshold_entity,
            self.cheapest_hours_count_entity,
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

        self._ensure_mode_initialized()
        just_reached = self._record_legionella_ok_if_reached(temp)
        # Don't re-read the helper we just wrote: the input_datetime state
        # update from call_service isn't guaranteed to be visible yet, which
        # would otherwise make the counter appear stuck at legionella_hybrid_days.
        days_since_ok = 0.0 if just_reached else self._days_since_legionella_ok()
        mode = self._get_mode()
        prices = self._get_prices()

        status_fields = dict(
            temp=temp,
            mode=mode,
            days_since_legionella_ok=days_since_ok,
            cheapest_hours_price_threshold=None,
            cheapest_hours_window_start=None,
            cheapest_hours_window_end=None,
        )
        if mode == "cheapest_hours":
            now = self.datetime()
            window_start, window_end = ch.price_window(now, self.cheapest_window_start_h)
            status_fields.update(
                cheapest_hours_price_threshold=ch.cheapest_hours_price_threshold(
                    prices, now, self._get_cheapest_hours_count(), self.cheapest_window_start_h,
                    ch.app_timezone(self),
                ),
                cheapest_hours_window_start=window_start.isoformat(),
                cheapest_hours_window_end=window_end.isoformat(),
            )

        # ── Priority 1: legionella boost deadline — always, unless user forced 'off' ──
        if days_since_ok >= self.legionella_boost_days and mode != "off":
            self.log(
                f"LEGIONELLA BOOST: {days_since_ok:.1f} days since last reaching "
                f"{self.legionella_temp:.0f}C — forcing boost"
            )
            self._apply("legionella_boost", "boost", **status_fields)
            return

        # ── Priority 2: forced user mode — always takes effect immediately ───
        if mode in ("off", "heatpump", "hybrid", "boost"):
            self.log(f"FORCE MODE: user selected '{mode}'")
            self._apply(f"force_{mode}", mode, **status_fields)
            return

        # Remaining branches are strategy-specific and price-driven
        now_hour = self.datetime().hour
        current_price = self._get_current_price(prices)

        self.log(f"Prices data: {type(prices).__name__} - {prices}", level="DEBUG")
        self.log(f"Current price: {current_price}", level="DEBUG")

        # ── Priority 3: legionella warning — escalate to hybrid during cheapest period only ──
        # Get live-tunable values
        live_threshold = self._get_market_price_threshold()
        live_cheapest_count = self._get_cheapest_hours_count()

        if days_since_ok >= self.legionella_hybrid_days:
            in_cheapest_period = False
            cheapest_period_label = "none"

            if mode == "market_price_threshold":
                in_cheapest_period = current_price is not None and current_price <= live_threshold
                cheapest_period_label = "below_threshold" if in_cheapest_period else "above_threshold"
            elif mode == "cheapest_hours":
                in_cheapest_period = self._is_cheapest_hour(prices, live_cheapest_count)
                cheapest_hours = self._cheapest_hours(prices, live_cheapest_count)
                cheapest_period_label = f"cheapest_{len(cheapest_hours)}h"

            if in_cheapest_period:
                self.log(
                    f"LEGIONELLA WARNING: {days_since_ok:.1f} days since last reaching "
                    f"{self.legionella_temp:.0f}C — cheapest={cheapest_period_label} — forcing hybrid"
                )
                price_fields = dict(
                    cheapest_period=cheapest_period_label,
                    in_cheapest_window=in_cheapest_period,
                    **status_fields,
                )
                self._apply("legionella_hybrid", "hybrid", **price_fields)
                return

        # ── Priority 4: market price threshold ──────────────────────────────
        if mode == "market_price_threshold":
            live_threshold = self._get_market_price_threshold()
            price_fields = dict(
                current_price=str(round(current_price, 4)) if current_price is not None else "N/A",
                threshold=str(live_threshold),
                **status_fields,
            )
            boiler_mode = "heatpump" if current_price is not None and current_price <= live_threshold else "off"
            self.log(
                f"MARKET PRICE THRESHOLD: current={current_price}, threshold={live_threshold} — mode={boiler_mode}"
            )
            self._apply(f"market_price_{boiler_mode}", boiler_mode, **price_fields)
            return

        # ── Priority 5: cheapest hours ───────────────────────────────────────
        if mode == "cheapest_hours":
            live_cheapest_count = self._get_cheapest_hours_count()
            cheapest_hours = self._cheapest_hours(prices, live_cheapest_count)
            in_cheapest_period = self._is_cheapest_hour(prices, live_cheapest_count)

            cheapest_hours_str = ",".join(str(h) for h in sorted(cheapest_hours))
            price_fields = dict(
                cheapest_hours=sorted(cheapest_hours),
                cheapest_hours_count=live_cheapest_count,
                in_cheapest_window=in_cheapest_period,
                **status_fields,
            )
            boiler_mode = "heatpump" if in_cheapest_period else "off"
            self.log(
                f"CHEAPEST HOURS: hour={now_hour}, cheapest_hours={cheapest_hours_str} — mode={boiler_mode}"
            )
            self._apply(f"cheapest_hours_{boiler_mode}", boiler_mode, **price_fields)
            return

    # ── Cheapest hours decision ─────────────────────────────────────────────

    def _is_cheapest_hour(self, prices, n_hours):
        """Whether the current hour ranks within the n cheapest of the shared price window."""
        return ch.is_cheapest_hour(
            prices, self.datetime(), n_hours, self.cheapest_window_start_h, ch.app_timezone(self)
        )

    def _cheapest_hours(self, prices, n_hours):
        """Clock hours (0-23) of the n cheapest hours in the shared price window."""
        hours = ch.cheapest_hours(
            prices, self.datetime(), n_hours, self.cheapest_window_start_h, ch.app_timezone(self)
        )
        return [h.hour for h in hours]

    def _get_current_price(self, prices=None):
        """
        Current price: the current local hour from the shared price data (same
        reading as the battery strategy), else current_price_sensor.
        """
        price = ch.price_at(prices, self.datetime(), ch.app_timezone(self))
        if price is not None:
            return price
        if not self.current_price_sensor:
            return None
        try:
            if self.current_price_attribute:
                price = self.get_state(self.current_price_sensor, attribute=self.current_price_attribute)
            else:
                price = self.get_state(self.current_price_sensor)
            if price is not None:
                return float(price)
            return None
        except Exception as e:
            self.log(f"Failed to get current price: {e}", level="DEBUG")
            return None

    # ── Legionella tracking ──────────────────────────────────────────────────

    def _record_legionella_ok_if_reached(self, temp: float) -> bool:
        """Stamp legionella_last_ok_entity with now whenever the boiler reaches legionella_temp.

        Returns True if the stamp was written this cycle.
        """
        if temp < self.legionella_temp:
            return False
        if not self.legionella_last_ok_entity:
            return False
        try:
            self.call_service(
                "input_datetime/set_datetime",
                entity_id=self.legionella_last_ok_entity,
                datetime=self.datetime().strftime("%Y-%m-%d %H:%M:%S"),
            )
            return True
        except Exception as e:
            self.log(f"Failed to stamp legionella_last_ok: {e}", level="WARNING")
            return False

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

    def _apply(self, branch: str, boiler_mode: str, **fields):
        """Publish the decided branch to the status sensor and set the boiler mode."""
        self._publish_status(branch, **fields)
        self._set_boiler_mode(boiler_mode)

    def _set_boiler_mode(self, option: str):
        if not self._entity_exists(self.boiler_mode_select):
            self.log("Boiler mode select entity not available", level="WARNING")
            return
        try:
            current = self.get_state(self.boiler_mode_select)
            # Only send on change: re-selecting 'boost' restarts the Ariston boost
            # sequence, and repeatedly restarting the heat pump damages it. The single
            # retry after a dropped boost is handled in HA (Boiler Boost Retry automation).
            if current != option:
                self.call_service(
                    "select/select_option",
                    entity_id=self.boiler_mode_select,
                    option=option,
                )
                self.log(f"Boiler mode → {option}")
        except Exception as e:
            self.log(f"Failed to set boiler mode: {e}", level="WARNING")

    # ── Sensor readers ────────────────────────────────────────────────────────

    def _ensure_mode_initialized(self):
        """
        Give the strategy mode a concrete value after a reboot leaves it unknown,
        and move a leftover retired mode (e.g. 'economic') to DEFAULT_MODE.
        """
        if not self.mode_select:
            return
        raw = self.get_state(self.mode_select)
        unset = raw in (None, "unknown", "unavailable", "")
        retired = not unset and str(raw).strip().lower() in RETIRED_MODES
        if unset or retired:
            reason = "unset" if unset else f"retired ('{raw}')"
            self.log(f"Strategy mode is {reason} — setting '{DEFAULT_MODE}'", level="WARNING")
            try:
                self.call_service(
                    "input_select/select_option",
                    entity_id=self.mode_select,
                    option=DEFAULT_MODE,
                )
            except Exception as e:
                self.log(f"Failed to initialize strategy mode: {e}", level="WARNING")

    def _get_mode(self) -> str:
        """User-selected strategy mode; DEFAULT_MODE when unset or retired."""
        if not self.mode_select:
            return DEFAULT_MODE
        raw = self.get_state(self.mode_select)
        if raw in (None, "unknown", "unavailable", ""):
            return DEFAULT_MODE
        mode = str(raw).strip().lower()
        return DEFAULT_MODE if mode in RETIRED_MODES else mode
    def _get_prices(self):
        """Hourly forecast prices or None.

        Sessy format: dict {ISO_timestamp: price, ...}; keys are UTC with offset
        and are converted to local hours by cheapest_hours.py.
        """
        if not self.price_forecast_sensor:
            return None
        try:
            return self.get_state(self.price_forecast_sensor, attribute=self.price_forecast_attribute)
        except Exception as e:
            self.log(f"Failed to get prices: {e}", level="DEBUG")
            return None

    def _get_market_price_threshold(self):
        """Get market price threshold from live entity or fallback to config."""
        if self.market_price_threshold_entity and self._entity_exists(self.market_price_threshold_entity):
            try:
                threshold = self.get_state(self.market_price_threshold_entity)
                if threshold is not None:
                    return float(threshold)
            except (TypeError, ValueError) as e:
                self.log(f"Failed to get live market_price_threshold: {e}", level="DEBUG")
        return self.market_price_threshold

    def _get_cheapest_hours_count(self):
        """Get cheapest hours count from live entity or fallback to config."""
        if self.cheapest_hours_count_entity and self._entity_exists(self.cheapest_hours_count_entity):
            try:
                count = self.get_state(self.cheapest_hours_count_entity)
                if count is not None:
                    return int(float(count))
            except (TypeError, ValueError) as e:
                self.log(f"Failed to get live cheapest_hours_count: {e}", level="DEBUG")
        return self.cheapest_hours_count

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
                    "rule_explanation": RULE_EXPLANATIONS.get(active_branch, "Unknown rule"),
                    **fields,
                },
            )
        except Exception as e:
            self.log(f"Failed to publish status: {e}", level="WARNING")