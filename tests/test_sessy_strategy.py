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
    prepeak_start=16,
    prepeak_end=18,
    prepeak_window_h=2.0,
    discharge_window_h=2.0,
    evening_peak_start=18,
    evening_peak_end=23,
    min_arbitrage_margin=0.05,
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
    app.initialize()
    return app


# ===========================================================================
# Setpoint calculators (pure math — no HA calls)
# ===========================================================================

class TestChargeSetpoint:
    def test_basic_gap(self):
        app = make_app()
        # gap = (90-50)/100 * 5000 = 2000 Wh; over 2h → 1000 W
        # cap = 0.40 * 5000 = 2000 W; max_power = 2200 → min is 1000
        result = app._charge_setpoint(soc=50, soc_target=90, prepeak_window_h=2.0)
        assert result == pytest.approx(1000.0)

    def test_capped_by_c_rate(self):
        app = make_app()
        # gap = (90-10)/100 * 5000 = 4000 Wh; over 1h → 4000 W
        # c_rate_cap = 0.40 * 5000 = 2000 W → capped at 2000
        result = app._charge_setpoint(soc=10, soc_target=90, prepeak_window_h=1.0)
        assert result == pytest.approx(2000.0)

    def test_minimum_50w(self):
        app = make_app()
        # Tiny gap: (90-89)/100 * 5000 = 50 Wh / 2h → 25 W; floor at 50
        result = app._charge_setpoint(soc=89, soc_target=90, prepeak_window_h=2.0)
        assert result == pytest.approx(50.0)


class TestDischargeSetpoint:
    def test_basic(self):
        app = make_app()
        # available = (80-20)/100 * 5000 = 3000 Wh / 2h → 1500 W
        result = app._discharge_setpoint(soc=80, soc_floor=20)
        assert result == pytest.approx(1500.0)

    def test_at_floor_returns_zero(self):
        app = make_app()
        result = app._discharge_setpoint(soc=20, soc_floor=20)
        assert result == 0

    def test_below_floor_returns_zero(self):
        app = make_app()
        result = app._discharge_setpoint(soc=15, soc_floor=20)
        assert result == 0

    def test_capped_by_max_power(self):
        app = make_app(max_power_w=500)
        result = app._discharge_setpoint(soc=80, soc_floor=20)
        assert result == pytest.approx(500.0)


class TestPostPeakDischargeSetpoint:
    def test_basic(self):
        # gap = (95-90)/100 * 5000 = 250 Wh / 4h → 62.5 W (above 50W floor)
        result = make_app()._post_peak_discharge_setpoint(soc=95, soc_target=90, hours_remaining=4)
        assert result == pytest.approx(62.5)

    def test_capped_by_c_rate(self):
        # gap = (100-20)/100 * 5000 = 4000 Wh / 1h → 4000 W; cap = 2000 W
        result = make_app()._post_peak_discharge_setpoint(soc=100, soc_target=20, hours_remaining=1)
        assert result == pytest.approx(2000.0)

    def test_minimum_50w(self):
        # tiny gap: (91-90)/100 * 5000 = 50 Wh / 4h → 12.5 W → floor at 50
        result = make_app()._post_peak_discharge_setpoint(soc=91, soc_target=90, hours_remaining=4)
        assert result == pytest.approx(50.0)


class TestCheapChargeSetpoint:
    def test_spreads_over_cheap_hours(self):
        app = make_app()
        # gap = (100-60)/100 * 5000 = 2000 Wh / 4h → 500 W
        result = app._cheap_charge_setpoint(soc=60, cheap_hours=4)
        assert result == pytest.approx(500.0)

    def test_already_at_ceiling_returns_zero(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=100, cheap_hours=3)
        assert result == 0

    def test_zero_cheap_hours_returns_zero(self):
        app = make_app()
        result = app._cheap_charge_setpoint(soc=50, cheap_hours=0)
        assert result == 0


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
        app._get_soc = MagicMock(return_value=soc)
        app._get_current_price = MagicMock(return_value=price)
        app.datetime = MagicMock(return_value=datetime(2024, 6, 15, now_hour, 0, 0))
        app._count_cheap_hours = MagicMock(return_value=2)
        app._max_price_in_window = MagicMock(return_value=0.50)
        app._get_prices_dict = MagicMock(return_value=None)
        app._publish_status = MagicMock()
        app._set_battery_setpoint = MagicMock()
        app._set_grid_setpoint = MagicMock()
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

    def test_priority3_prepeak_window_charges(self):
        # 17:00, SOC below target, spread > margin
        app = self._make_app_with_sensors(soc=60, price=0.10, now_hour=17)
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once()
        assert app._set_battery_setpoint.call_args[0][0] < 0

    def test_priority3_prepeak_skipped_when_spread_too_small(self):
        app = self._make_app_with_sensors(soc=60, price=0.10, now_hour=17)
        # import_price = 0.10 + 0.11 = 0.21; expected_peak = 0.22 → spread 0.01 < margin 0.05
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
        # 19:00, after prepeak_end (18), soc above target, no spike coming
        app = self._make_app_with_sensors(soc=95, price=0.20, now_hour=19)
        app._max_price_in_window = MagicMock(return_value=0.30)  # below price_discharge (0.39)
        app.update_strategy({})
        app._set_battery_setpoint.assert_called_once()
        assert app._set_battery_setpoint.call_args[0][0] > 0  # discharge → positive watts
        app._set_grid_setpoint.assert_not_called()

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

    def test_priority3_prepeak_at_target_holds_grid_zero(self):
        # SOC already at soc_target during prepeak window → no charge needed
        app = self._make_app_with_sensors(soc=90, price=0.10, now_hour=17)
        app.update_strategy({})
        app._set_grid_setpoint.assert_called_once_with(0)
        app._set_battery_setpoint.assert_not_called()


# ===========================================================================
# Enable switch
# ===========================================================================

class TestEnableSwitch:
    def test_switch_off_skips_cycle(self):
        app = make_app(enable_switch="input_boolean.sessy_strategy_enabled")
        app.get_state = MagicMock(return_value="off")
        app._set_grid_setpoint = MagicMock()
        app._set_battery_setpoint = MagicMock()
        app.update_strategy({})
        app._set_grid_setpoint.assert_not_called()
        app._set_battery_setpoint.assert_not_called()


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

    def test_entity_overrides_config_mode(self):
        app = make_app(season_mode="auto", season_mode_entity="input_select.sessy_season_mode")
        app.get_state = MagicMock(return_value="winter")
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

    # _get_current_price
    def test_get_price_from_attribute_dict(self):
        # Attribute dict contains the current hour key → read from there
        app = make_app()
        app.get_state = MagicMock(return_value={"2024-06-15T14:00:00": 0.25})
        assert app._get_current_price() == pytest.approx(0.25)

    def test_get_price_fallback_to_sensor_state(self):
        # No attribute dict → fall through to the sensor state value
        app = make_app()
        app.get_state = MagicMock(side_effect=[None, "0.30"])
        assert app._get_current_price() == pytest.approx(0.30)

    def test_get_price_unavailable_returns_none(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        assert app._get_current_price() is None

    # _count_cheap_hours
    def test_count_cheap_hours_consecutive(self):
        # Hours 14 and 15 are cheap; 16 is not → count = 2
        app = make_app()
        prices = {
            "2024-06-15T14:00:00": -0.20,
            "2024-06-15T15:00:00": -0.15,
            "2024-06-15T16:00:00": 0.10,
        }
        app._get_prices_dict = MagicMock(return_value=prices)
        assert app._count_cheap_hours(-0.10) == 2

    def test_count_cheap_hours_none_below_threshold_returns_one(self):
        # No cheap hours → minimum of 1 so callers never divide by zero
        app = make_app()
        app._get_prices_dict = MagicMock(return_value={"2024-06-15T14:00:00": 0.20})
        assert app._count_cheap_hours(-0.10) == 1

    def test_count_cheap_hours_no_prices_returns_one(self):
        app = make_app()
        app._get_prices_dict = MagicMock(return_value=None)
        assert app._count_cheap_hours(-0.10) == 1

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
            active_season="summer",
            min_price_hour=12,
            min_price_value=0.05,
            soc=75.0,
            raw_price=0.20,
            import_price=0.31,
            soc_target=90.0,
            soc_floor=20.0,
            price_discharge=0.39,
            price_charge=-0.10,
            min_arbitrage_margin=0.05,
            prepeak_start=16,
            prepeak_end=18,
            prepeak_window_h=2.0,
        )

    def test_writes_state_and_attributes(self):
        app = make_app()
        self._call_publish(app)
        app.set_state.assert_called_once()
        kwargs = app.set_state.call_args.kwargs
        assert kwargs["state"] == "summer"
        assert kwargs["attributes"]["soc"] == pytest.approx(75.0)
        assert kwargs["attributes"]["raw_price"] == pytest.approx(0.20)

    def test_skipped_when_status_sensor_unset(self):
        app = make_app()
        app.status_sensor = None
        self._call_publish(app)
        app.set_state.assert_not_called()
