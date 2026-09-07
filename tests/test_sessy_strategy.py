"""
Tests for SessyStrategy.

AppDaemon is not installed locally, so we stub the hass.Hass base class before
importing the module under test. All HA calls (get_state, call_service, etc.)
are replaced with unittest.mock.MagicMock instances so each test can configure
exactly what the "HA world" looks like.
"""

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Stub the appdaemon package so the import in sessy_strategy.py succeeds
# ---------------------------------------------------------------------------

class _FakeHass:
    """Minimal stand-in for appdaemon.plugins.hass.hassapi.Hass."""
    args = {}

    def log(self, *a, **kw):
        pass

    def get_state(self, *a, **kw):
        return None

    def call_service(self, *a, **kw):
        pass

    def set_state(self, *a, **kw):
        pass

    def datetime(self):
        return datetime(2024, 6, 15, 14, 0, 0)  # summer, 14:00

    def run_every(self, *a, **kw):
        pass

    def run_in(self, *a, **kw):
        pass

    def listen_state(self, *a, **kw):
        pass


_hass_module        = types.ModuleType("appdaemon")
_plugins_module     = types.ModuleType("appdaemon.plugins")
_hass_plugin_module = types.ModuleType("appdaemon.plugins.hass")
_hassapi_module     = types.ModuleType("appdaemon.plugins.hass.hassapi")
_hassapi_module.Hass = _FakeHass

sys.modules["appdaemon"]                        = _hass_module
sys.modules["appdaemon.plugins"]                = _plugins_module
sys.modules["appdaemon.plugins.hass"]           = _hass_plugin_module
sys.modules["appdaemon.plugins.hass.hassapi"]   = _hassapi_module

# Now the real import works
sys.path.insert(0, "files")
from sessy_strategy import SessyStrategy  # noqa: E402


# ---------------------------------------------------------------------------
# Factory — builds a fully-initialized SessyStrategy without running
# AppDaemon's scheduling. Pass keyword args to override any apps.yaml default.
# ---------------------------------------------------------------------------

_DEFAULTS = dict(
    capacity_wh=5000,
    max_power_w=2200,
    c_rate_cap=0.40,
    soc_target=90,
    soc_floor=20,
    cheap_soc_target=100,
    surcharge=0.11,
    price_discharge=0.39,
    price_charge=-0.10,
    afternoon_start=16,
    afternoon_end=18,
    afternoon_window_h=2.0,
    discharge_window_h=2.0,
    evening_peak_start=18,
    evening_peak_end=23,
    min_arbitrage_margin=0.05,
    afternoon_margin=0.05,
    season_mode="summer",
    season_day_start=8,
    season_day_end=18,
    season_auto_fallback="winter",
)


def make_app(**overrides):
    """Return a SessyStrategy instance with initialize() called."""
    app = SessyStrategy.__new__(SessyStrategy)
    app.args = {**_DEFAULTS, **overrides}
    app.log = MagicMock()
    app.get_state = MagicMock(return_value=None)
    app.call_service = MagicMock()
    app.set_state = MagicMock()
    app.datetime = MagicMock(return_value=datetime(2024, 6, 15, 14, 0, 0))
    app.run_every = MagicMock()
    app.run_in = MagicMock()
    app.listen_state = MagicMock()
    app.initialize()
    return app


# ===========================================================================
# Setpoint calculators (pure math — no HA calls)
# ===========================================================================

class TestDischargeSetpoint:
    def test_basic(self):
        app = make_app()
        # available = (80-20)/100 * 5000 = 3000 Wh / 2h → 1500 W
        result = app._discharge_setpoint(soc=80, soc_floor=20, window_h=2.0)
        assert result == pytest.approx(1500.0)

    def test_at_floor_returns_zero(self):
        app = make_app()
        result = app._discharge_setpoint(soc=20, soc_floor=20, window_h=2.0)
        assert result == 0

    def test_below_floor_returns_zero(self):
        app = make_app()
        result = app._discharge_setpoint(soc=15, soc_floor=20, window_h=2.0)
        assert result == 0

    def test_capped_by_max_power(self):
        app = make_app(max_power_w=500)
        result = app._discharge_setpoint(soc=80, soc_floor=20, window_h=2.0)
        assert result == pytest.approx(500.0)


class TestExcessSetpoint:
    def test_basic(self):
        # gap = (95-90)/100 * 5000 = 250 Wh / 4h → 62.5 W → floored at 500W
        result = make_app()._excess_setpoint(soc=95, target=90, hours_remaining=4)
        assert result == pytest.approx(500.0)

    def test_capped_by_max_power(self):
        # gap = (100-20)/100 * 5000 = 4000 Wh / 1h → 4000 W; cap = max_power_w = 2200 W
        result = make_app()._excess_setpoint(soc=100, target=20, hours_remaining=1)
        assert result == pytest.approx(2200.0)

    def test_minimum_500w(self):
        # tiny gap: (91-90)/100 * 5000 = 50 Wh / 4h → 12.5 W → floor at 500
        result = make_app()._excess_setpoint(soc=91, target=90, hours_remaining=4)
        assert result == pytest.approx(500.0)

    def test_at_or_below_target_returns_zero(self):
        result = make_app()._excess_setpoint(soc=90, target=90, hours_remaining=4)
        assert result == 0


class TestCheapChargeSetpoint:
    def test_charges_at_max_power_when_below_target(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=60, cheap_soc_target=100, window_h=4)
        assert result == app.max_power_w

    def test_already_at_ceiling_returns_zero(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=100, cheap_soc_target=100, window_h=3)
        assert result == 0

    def test_charges_at_max_power_regardless_of_window(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=50, cheap_soc_target=100, window_h=0)
        assert result == app.max_power_w

    def test_charges_at_max_power_with_lower_ceiling(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=60, cheap_soc_target=80, window_h=2)
        assert result == app.max_power_w


# ===========================================================================
# Seasonal helpers
# ===========================================================================

class TestSeasonalValue:
    def test_summer_returns_base(self):
        app = make_app()
        assert app._seasonal_value(20, "summer", 30) == 20

    def test_winter_with_override_returns_override(self):
        app = make_app()
        assert app._seasonal_value(20, "winter", 30) == 30

    def test_winter_without_override_returns_base(self):
        app = make_app()
        assert app._seasonal_value(20, "winter", None) == 20


# ===========================================================================
# update_strategy — decision branches
# ===========================================================================

class TestUpdateStrategyBranches:
    """
    Each test patches the sensor readers and asserts which actuator was called.
    We do NOT test exact watt values here — that is covered by the setpoint tests.
    """

    def _make_app_with_sensors(self, soc, price, now_hour=14):
        app = make_app()
        # Mock entity existence checks
        app.get_state = MagicMock(side_effect=lambda entity_id, **kwargs: {
            app.soc_sensor: str(soc) if soc is not None else None,
            app.price_sensor: str(price) if price is not None else None,
            app.strategy_select: "nom",
            app.grid_target: "0",
            app.battery_setpoint: "0",
        }.get(entity_id, None))

        app._get_soc = MagicMock(return_value=soc)
        app._current_price = MagicMock(return_value=price)
        app.datetime = MagicMock(return_value=datetime(2024, 6, 15, now_hour, 0, 0))
        app._count_cheap_hours = MagicMock(return_value=2)
        app._max_price_in_window = MagicMock(return_value=0.50)
        app._max_price_in_hour_range_tomorrow = MagicMock(return_value=None)
        app._get_prices_dict = MagicMock(return_value=None)
        app._publish_status = MagicMock()
        app._set_battery_setpoint = MagicMock()
        app._set_grid_setpoint = MagicMock()
        app._apply_standby = MagicMock()
        return app

    def test_priority1_high_price_triggers_discharge(self):
        app = self._make_app_with_sensors(soc=80, price=0.45)
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once()
        # discharge → positive watts
        assert app._set_battery_setpoint.call_args[0][0] > 0
        app._set_grid_setpoint.assert_not_called()

    def test_priority2_cheap_price_triggers_charge(self):
        app = self._make_app_with_sensors(soc=50, price=-0.20)
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once()
        # charge → negative watts
        assert app._set_battery_setpoint.call_args[0][0] < 0

    def test_priority2_cheap_price_at_ceiling_holds_grid_zero(self):
        app = self._make_app_with_sensors(soc=100, price=-0.20)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_priority3_afternoon_window_charges(self):
        # 17:00, SOC below target, spread > margin
        app = self._make_app_with_sensors(soc=60, price=0.10, now_hour=17)
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once()
        assert app._set_battery_setpoint.call_args[0][0] < 0

    def test_priority3_afternoon_skipped_when_spread_too_small(self):
        app = self._make_app_with_sensors(soc=60, price=0.20, now_hour=17)
        # buy = 0.20; evening peak buy = 0.22 → spread 0.02 < margin 0.05
        app._max_price_in_window = MagicMock(return_value=0.22)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_priority4_default_sets_grid_zero(self):
        # Normal hour (14:00), normal price
        app = self._make_app_with_sensors(soc=80, price=0.15)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_missing_soc_skips_cycle(self):
        app = self._make_app_with_sensors(soc=None, price=0.15)
        app.update_strategy({})
        app._set_grid_setpoint.assert_not_called()
        app._set_battery_setpoint.assert_not_called()

    def test_priority35_post_peak_discharges_to_target(self):
        # 19:00, after afternoon_end (18), soc above target, no spike coming
        app = self._make_app_with_sensors(soc=95, price=0.20, now_hour=19)
        app._max_price_in_window = MagicMock(return_value=0.30)  # below price_discharge (0.39)
        app.update_strategy({})
        # Sells the excess via a negative grid setpoint (negative = export) so the
        # battery covers home load on top and never imports to top up.
        app._set_grid_setpoint.assert_called_once()
        assert app._set_grid_setpoint.call_args[0][0] < 0  # export → negative watts
        app._set_battery_setpoint.assert_not_called()

    def test_priority35_skipped_when_spike_coming(self):
        # max remaining price > price_discharge → skip, fall through to default
        app = self._make_app_with_sensors(soc=95, price=0.20, now_hour=19)
        app._max_price_in_window = MagicMock(return_value=0.45)  # above price_discharge (0.39)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_priority35_skipped_when_soc_at_target(self):
        # soc == soc_target → condition soc > soc_target is False → default
        app = self._make_app_with_sensors(soc=90, price=0.20, now_hour=19)
        app._max_price_in_window = MagicMock(return_value=0.30)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_priority35_skipped_outside_evening_peak_window(self):
        # now_hour=23 == evening_peak_end → excluded by < evening_peak_end
        app = self._make_app_with_sensors(soc=95, price=0.20, now_hour=23)
        app._max_price_in_window = MagicMock(return_value=0.30)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_priority3_afternoon_at_target_holds_grid_zero(self):
        # SOC already at soc_target during afternoon window → no charge needed
        app = self._make_app_with_sensors(soc=90, price=0.10, now_hour=17)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()

    def test_rule_disabled_skips_price_spike(self):
        # Price-spike rule off → high price no longer discharges, falls through
        app = self._make_app_with_sensors(soc=80, price=0.45)
        app.rule_price_spike_entity = "switch.home_battery_rule_price_spike"
        app._rule_enabled = MagicMock(
            side_effect=lambda e: e != "switch.home_battery_rule_price_spike"
        )
        app.update_strategy({})
        app._set_battery_setpoint.assert_not_called()
        app._set_grid_setpoint.assert_called_once_with(0)

    def test_priority5_morning_selloff_discharges(self):
        # 08:00 within morning window [7,9); SOC 80 > target_morning_soc 30
        app = self._make_app_with_sensors(soc=80, price=0.10, now_hour=8)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once()
        assert app._set_grid_setpoint.call_args[0][0] < 0  # export → negative watts
        app._set_battery_setpoint.assert_not_called()

    def test_priority4_holds_for_better_morning(self):
        # No evening spike, but tomorrow's morning peak is clearly better → hold
        app = self._make_app_with_sensors(soc=95, price=0.20, now_hour=19)
        app._max_price_in_window = MagicMock(return_value=0.30)
        app._max_price_in_hour_range_tomorrow = MagicMock(return_value=0.40)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()


# ===========================================================================
# Per-rule enable switches
# ===========================================================================

class TestRuleEnabled:
    def test_no_entity_is_enabled(self):
        assert make_app()._rule_enabled(None) is True

    def test_on_is_enabled(self):
        app = make_app()
        app.get_state = MagicMock(return_value="on")
        assert app._rule_enabled("switch.x") is True

    def test_off_is_disabled(self):
        app = make_app()
        app.get_state = MagicMock(return_value="off")
        assert app._rule_enabled("switch.x") is False

    def test_unreadable_defaults_enabled(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        assert app._rule_enabled("switch.x") is True


# ===========================================================================
# Grid-connection guard clamp
# ===========================================================================

class TestGridGuard:
    def test_grid_export_clamped_to_limit(self):
        app = make_app(max_grid_w=8000, grid_utilization=0.9)
        assert app._clamp_to_grid_limit(-9000, "grid") == pytest.approx(-7200)

    def test_grid_import_clamped_to_limit(self):
        app = make_app(max_grid_w=8000, grid_utilization=0.9)
        assert app._clamp_to_grid_limit(9000, "grid") == pytest.approx(7200)

    def test_within_limit_unchanged(self):
        app = make_app(max_grid_w=8000, grid_utilization=0.9)
        assert app._clamp_to_grid_limit(-2000, "grid") == pytest.approx(-2000)

    def test_battery_clamped_to_max_power(self):
        app = make_app(max_power_w=2200, max_grid_w=8000, grid_utilization=0.9)
        assert app._clamp_to_grid_limit(-5000, "battery") == pytest.approx(-2200)


# ===========================================================================
# Operating-mode selector (master control)
# ===========================================================================

class TestModeSelector:
    """
    The mode selector gates the whole cycle.
    Each test stubs the actuators and asserts the app honours the selected mode.
    """

    def _make(self, mode_state, **overrides):
        app = make_app(
            mode_select="input_select.home_battery_mode",
            setpoint_entity="input_number.home_battery_setpoint",
            **overrides,
        )
        app._set_grid_setpoint = MagicMock()
        app._set_battery_setpoint = MagicMock()
        app._publish_branch = MagicMock()
        app._apply_standby = MagicMock()
        app._entity_exists = MagicMock(return_value=True)
        # _get_soc/_current_price only needed by the optimized chain.
        app._get_soc = MagicMock(return_value=80)
        app._current_price = MagicMock(return_value=0.15)
        app._get_prices_dict = MagicMock(return_value=None)
        app._max_price_in_window = MagicMock(return_value=0.50)
        app._max_price_in_hour_range_tomorrow = MagicMock(return_value=None)
        app._publish_status = MagicMock()
        # get_state resolves both the selector and any input_number reads.
        def _get_state(entity_id=None, *a, **kw):
            if entity_id == "input_select.home_battery_mode":
                return mode_state
            if entity_id == "input_number.home_battery_setpoint":
                return "-500"
            return None
        app.get_state = MagicMock(side_effect=_get_state)
        return app

    def test_label_is_normalised(self):
        # "Grid setpoint" → grid_setpoint
        assert self._make("Grid setpoint")._active_mode() == "grid_setpoint"

    def test_optimized_runs_priority_chain(self):
        app = self._make("Optimized")
        app.update_strategy({})
        # 14:00 / SOC 80 / 0.15 → default branch sets grid 0
        app._set_grid_setpoint.assert_called_once_with(0)

    def test_grid_setpoint_mode_applies_setpoint_to_grid(self):
        app = self._make("Grid setpoint")
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(-500.0)
        app._set_battery_setpoint.assert_not_called()

    def test_battery_setpoint_mode_applies_setpoint_to_battery(self):
        app = self._make("Battery setpoint")
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once_with(-500.0)
        app._set_grid_setpoint.assert_not_called()

    def test_sessy_dynamic_stands_down(self):
        app = self._make("Sessy dynamic")
        app.update_strategy({})
        app._apply_standby.assert_called_once_with(app.sessy_dynamic_option, "sessy_dynamic")
        app._set_grid_setpoint.assert_not_called()
        app._set_battery_setpoint.assert_not_called()

    def test_eco_stands_down(self):
        app = self._make("Eco")
        app.update_strategy({})
        app._apply_standby.assert_called_once_with(app.eco_option, "eco")
        app._set_grid_setpoint.assert_not_called()
        app._set_battery_setpoint.assert_not_called()

    def test_idle_stands_down(self):
        app = self._make("Idle")
        app.update_strategy({})
        app._apply_standby.assert_called_once_with(app.idle_option, "idle")
        app._set_grid_setpoint.assert_not_called()
        app._set_battery_setpoint.assert_not_called()

    def test_unknown_label_falls_back_to_optimized(self):
        app = self._make("Bogus")
        assert app._active_mode() == "optimized"


class TestApplyStandby:
    def test_switches_strategy_when_different(self):
        app = make_app()
        app.get_state = MagicMock(return_value="api")
        app.call_service = MagicMock()
        app._publish_branch = MagicMock()
        app._apply_standby("roi", "sessy_dynamic")
        app.call_service.assert_called_once_with(
            "select/select_option",
            entity_id=app.strategy_select,
            option="roi",
        )
        app._publish_branch.assert_called_once_with("sessy_dynamic", sessy_strategy="roi")

    def test_no_switch_when_already_on_option(self):
        app = make_app()
        app.get_state = MagicMock(return_value="roi")
        app.call_service = MagicMock()
        app._publish_branch = MagicMock()
        app._apply_standby("roi", "sessy_dynamic")
        app.call_service.assert_not_called()
        app._publish_branch.assert_called_once()


class TestPublishBranch:
    def test_writes_branch_state_and_extra(self):
        app = make_app()
        app._entity_exists = MagicMock(return_value=True)
        app.set_state = MagicMock()
        app._publish_branch("manual_grid", setpoint=-500.0)
        kwargs = app.set_state.call_args.kwargs
        assert kwargs["state"] == "manual_grid"
        assert kwargs["attributes"]["active_branch"] == "manual_grid"
        assert kwargs["attributes"]["setpoint"] == pytest.approx(-500.0)

    def test_skipped_when_status_sensor_unset(self):
        app = make_app()
        app.status_sensor = None
        app.set_state = MagicMock()
        app._publish_branch("idle")
        app.set_state.assert_not_called()


# ===========================================================================
# Tunable live-override helper
# ===========================================================================

class TestTunable:
    def test_no_entity_returns_default(self):
        assert make_app()._tunable(90.0, None) == pytest.approx(90.0)

    def test_entity_readable_returns_float(self):
        app = make_app()
        app.get_state = MagicMock(return_value="85.5")
        assert app._tunable(90.0, "input_number.foo") == pytest.approx(85.5)

    def test_entity_unreadable_returns_default(self):
        app = make_app()
        app.get_state = MagicMock(return_value="unavailable")
        assert app._tunable(90.0, "input_number.foo") == pytest.approx(90.0)


# ===========================================================================
# Season mode inference
# ===========================================================================

class TestActiveSeasonMode:
    def _prices_with_min_at(self, hour: int):
        return {f"2024-06-15T{h:02d}:00:00": (0.05 if h == hour else 0.30) for h in range(24)}

    def test_explicit_summer(self):
        assert make_app(season_mode="summer")._active_season_mode() == "summer"

    def test_explicit_winter(self):
        assert make_app(season_mode="winter")._active_season_mode() == "winter"

    def test_auto_daytime_min_infers_summer(self):
        # Minimum price at 12:00 (inside season_day_start=8 … season_day_end=18) → summer
        app = make_app(season_mode="auto")
        app._get_prices_dict = MagicMock(return_value=self._prices_with_min_at(12))
        assert app._active_season_mode() == "summer"

    def test_auto_nighttime_min_infers_winter(self):
        # Minimum price at 02:00 (outside daytime window) → winter
        app = make_app(season_mode="auto")
        app._get_prices_dict = MagicMock(return_value=self._prices_with_min_at(2))
        assert app._active_season_mode() == "winter"

    def test_auto_falls_back_when_no_prices(self):
        app = make_app(season_mode="auto", season_auto_fallback="winter")
        app._get_prices_dict = MagicMock(return_value=None)
        assert app._active_season_mode() == "winter"


# ===========================================================================
# Sensor readers
# ===========================================================================

class TestSensorReaders:
    # _get_soc
    def test_get_soc_valid(self):
        app = make_app()
        app.get_state = MagicMock(return_value="75.5")
        assert app._get_soc() == pytest.approx(75.5)

    def test_get_soc_none_returns_none(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        assert app._get_soc() is None

    def test_get_soc_unavailable_returns_none(self):
        app = make_app()
        app.get_state = MagicMock(return_value="unavailable")
        assert app._get_soc() is None

    # _current_price
    def test_get_price_from_attribute_dict(self):
        # Attribute dict contains the current hour key → read from there
        app = make_app()
        app.get_state = MagicMock(return_value={"2024-06-15T14:00:00": 0.25})
        assert app._current_price("sell") == pytest.approx(0.25)

    def test_get_price_fallback_to_sensor_state(self):
        # No attribute dict → fall through to the sensor state value
        app = make_app()
        app.get_state = MagicMock(side_effect=[None, "0.30"])
        assert app._current_price("sell") == pytest.approx(0.30)

    def test_get_price_unavailable_returns_none(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        assert app._current_price("sell") is None

    # _contiguous_price_hours (renamed from _count_cheap_hours)
    def test_count_cheap_hours_consecutive(self):
        # Hours 14 and 15 are cheap; 16 is not → count = 2
        app = make_app()
        prices = {
            "2024-06-15T14:00:00": -0.20,
            "2024-06-15T15:00:00": -0.15,
            "2024-06-15T16:00:00": 0.10,
        }
        app._get_prices_dict = MagicMock(return_value=prices)
        assert app._contiguous_price_hours(-0.10, above=False) == 2

    def test_count_cheap_hours_none_below_threshold_returns_one(self):
        # No cheap hours → minimum of 1 so callers never divide by zero
        app = make_app()
        app._get_prices_dict = MagicMock(return_value={"2024-06-15T14:00:00": 0.20})
        assert app._contiguous_price_hours(-0.10, above=False) == 1

    def test_count_cheap_hours_no_prices_returns_one(self):
        app = make_app()
        app._get_prices_dict = MagicMock(return_value=None)
        assert app._contiguous_price_hours(-0.10, above=False) == 1

    # _max_price_in_window
    def test_max_price_in_window_normal(self):
        app = make_app()
        prices = {
            "2024-06-15T18:00:00": 0.35,
            "2024-06-15T19:00:00": 0.45,
            "2024-06-15T20:00:00": 0.40,
        }
        app._get_prices_dict = MagicMock(return_value=prices)
        assert app._max_price_in_window(18, 21) == pytest.approx(0.45)

    def test_max_price_no_prices_returns_none(self):
        app = make_app()
        app._get_prices_dict = MagicMock(return_value=None)
        assert app._max_price_in_window(18, 23) is None

    def test_max_price_empty_window_returns_none(self):
        app = make_app()
        app._get_prices_dict = MagicMock(return_value={})
        assert app._max_price_in_window(18, 23) is None

    # _daily_min_price_hour_and_value
    def test_daily_min_price_finds_correct_hour(self):
        app = make_app()
        prices = {f"2024-06-15T{h:02d}:00:00": (0.05 if h == 12 else 0.30) for h in range(24)}
        app._get_prices_dict = MagicMock(return_value=prices)
        hour, value = app._daily_min_price_hour_and_value()
        assert hour == 12
        assert value == pytest.approx(0.05)

    def test_daily_min_price_no_prices_returns_none_pair(self):
        app = make_app()
        app._get_prices_dict = MagicMock(return_value=None)
        assert app._daily_min_price_hour_and_value() == (None, None)


# ===========================================================================
# Status publishing
# ===========================================================================

class TestPublishStatus:
    def _call_publish(self, app):
        app._publish_status(
            "default",
            active_season="summer",
            min_price_hour=12,
            min_price_value=0.05,
            soc=75.0,
            raw_price=0.20,
            import_price=0.31,
            soc_target=90.0,
            soc_floor=20.0,
            cheap_soc_target=100.0,
            price_discharge=0.39,
            price_charge=-0.10,
            min_arbitrage_margin=0.05,
            afternoon_margin=0.05,
            afternoon_start=16,
            afternoon_end=18,
            afternoon_window_h=2.0,
        )

    def test_writes_state_and_attributes(self):
        app = make_app()
        app._entity_exists = MagicMock(return_value=True)
        self._call_publish(app)
        app.set_state.assert_called_once()
        kwargs = app.set_state.call_args.kwargs
        assert kwargs["state"] == "summer"
        assert kwargs["attributes"]["active_branch"] == "default"
        assert kwargs["attributes"]["soc"] == pytest.approx(75.0)
        assert kwargs["attributes"]["raw_price"] == pytest.approx(0.20)
        assert kwargs["attributes"]["cheap_soc_target"] == pytest.approx(100.0)

    def test_skipped_when_status_sensor_unset(self):
        app = make_app()
        app.status_sensor = None
        self._call_publish(app)
        app.set_state.assert_not_called()
