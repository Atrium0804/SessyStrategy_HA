"""
Tests for BoilerStrategy.

AppDaemon is not installed locally, so we stub the hass.Hass base class before
importing the module under test (mirrors tests/test_sessy_strategy.py).
"""

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock
import pytest


class _FakeHass:
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
        return datetime(2024, 6, 15, 14, 0, 0)

    def run_every(self, *a, **kw):
        pass

    def run_in(self, *a, **kw):
        pass

    def listen_state(self, *a, **kw):
        pass

    def cancel_timer(self, *a, **kw):
        pass


if "appdaemon.plugins.hass.hassapi" not in sys.modules:
    _hass_module        = types.ModuleType("appdaemon")
    _plugins_module     = types.ModuleType("appdaemon.plugins")
    _hass_plugin_module = types.ModuleType("appdaemon.plugins.hass")
    _hassapi_module     = types.ModuleType("appdaemon.plugins.hass.hassapi")
    _hassapi_module.Hass = _FakeHass

    sys.modules["appdaemon"]                      = _hass_module
    sys.modules["appdaemon.plugins"]              = _plugins_module
    sys.modules["appdaemon.plugins.hass"]         = _hass_plugin_module
    sys.modules["appdaemon.plugins.hass.hassapi"] = _hassapi_module
else:
    sys.modules["appdaemon.plugins.hass.hassapi"].Hass = _FakeHass

sys.path.insert(0, "files")
from boiler_strategy import BoilerStrategy  # noqa: E402


_DEFAULTS = dict(
    legionella_temp=65,
    legionella_hybrid_days=6,
    legionella_boost_days=7,
    economic_day_start=10,
    economic_day_end=16,
    economic_night_start=0,
    economic_night_end=6,
)


def make_app(**overrides):
    app = BoilerStrategy.__new__(BoilerStrategy)
    app.args = {**_DEFAULTS, **overrides}
    app.log = MagicMock()
    app.get_state = MagicMock(return_value=None)
    app.call_service = MagicMock()
    app.set_state = MagicMock()
    app.datetime = MagicMock(return_value=datetime(2024, 6, 15, 14, 0, 0))
    app.run_every = MagicMock()
    app.run_in = MagicMock()
    app.listen_state = MagicMock()
    app.cancel_timer = MagicMock()
    app.initialize()
    return app


# ===========================================================================
# Legionella tracking
# ===========================================================================

class TestLegionellaTracking:
    def test_days_since_ok_no_helper_configured(self):
        app = make_app(legionella_last_ok_entity=None)
        assert app._days_since_legionella_ok() == pytest.approx(6)

    def test_days_since_ok_unknown_state_defaults_to_hybrid_days(self):
        app = make_app()
        app.get_state = MagicMock(return_value="unknown")
        assert app._days_since_legionella_ok() == pytest.approx(6)

    def test_days_since_ok_computed_from_timestamp(self):
        app = make_app()
        app.get_state = MagicMock(return_value="2024-06-10 14:00:00")
        # 2024-06-15 14:00:00 - 2024-06-10 14:00:00 = 5 days
        assert app._days_since_legionella_ok() == pytest.approx(5.0)

    def test_record_legionella_ok_stamps_when_temp_reached(self):
        app = make_app()
        app._record_legionella_ok_if_reached(65.0)
        app.call_service.assert_called_once_with(
            "input_datetime/set_datetime",
            entity_id="input_datetime.boiler_legionella_last_ok",
            datetime="2024-06-15 14:00:00",
        )

    def test_record_legionella_ok_skips_when_temp_below_threshold(self):
        app = make_app()
        app._record_legionella_ok_if_reached(64.9)
        app.call_service.assert_not_called()


# ===========================================================================
# update_strategy priority chain
# ===========================================================================

def _sessy_prices(price, hours):
    return {f"2024-06-15T{h:02d}:00:00": price for h in hours}


def _entity_states(temp, mode="economic", prices=None, legionella_last_ok=None,
                   boiler_mode="init", current_price=None):
    states = {
        "sensor.boiler_temperatuur": str(temp),
        "input_select.boiler_strategy_mode": mode,
        "input_datetime.boiler_legionella_last_ok": legionella_last_ok,
        "select.boiler_mode": boiler_mode,
        "sensor.boiler_strategy_status": "ok",
    }

    def _get_state(entity_id=None, attribute=None):
        if entity_id == "sensor.sessy_dnhh_energy_price" and attribute == "energy_prices":
            return prices
        if entity_id == "sensor.current_energy_price":
            return current_price
        return states.get(entity_id)

    return _get_state


# Cheaper morning window (0-6) vs pricier midday window (10-16).
_MORNING_CHEAP = {**_sessy_prices(0.05, range(0, 6)), **_sessy_prices(0.30, range(10, 16))}
# Cheaper midday window (10-16) vs pricier morning window (0-6).
_MIDDAY_CHEAP = {**_sessy_prices(0.30, range(0, 6)), **_sessy_prices(0.05, range(10, 16))}


class TestUpdateStrategyPriority:
    # ── Legionella boost overrides any user mode except 'off' ────────────────
    def test_legionella_boost_forces_boost_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="economic",
            legionella_last_ok="2024-06-07 14:00:00",  # 8 days ago
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="boost"
        )

    def test_legionella_hybrid_warning_forces_hybrid_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="economic", prices=_MIDDAY_CHEAP,
            legionella_last_ok="2024-06-09 14:00:00",  # 6 days ago; clock=14:00 is inside the cheaper midday window
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="hybrid"
        )

    def test_forced_mode_beats_legionella_hybrid_warning(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="heatpump",
            legionella_last_ok="2024-06-09 14:00:00",  # 6 days ago -> hybrid warning active
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    # ── Forced user modes ────────────────────────────────────────────────────
    def test_force_heatpump_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="heatpump", legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    def test_force_hybrid_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="hybrid", legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="hybrid"
        )

    def test_force_boost_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="boost", legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="boost"
        )

    # ── Economic mode (fixed clock = 14:00, i.e. inside the 10-16 window) ────
    def test_economic_heatpump_when_now_in_cheapest_window(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="economic", prices=_MIDDAY_CHEAP,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    def test_economic_off_when_now_outside_cheapest_window(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="economic", prices=_MORNING_CHEAP,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="off"
        )

    def test_economic_off_when_no_forecast(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="economic", prices=None,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="off"
        )

    def test_market_price_threshold_includes_price_equal_to_threshold(self):
        app = make_app(
            market_price_threshold=0.1,
            current_price_sensor="sensor.current_energy_price",
            current_price_attribute="",
        )
        app.get_state = _entity_states(
            temp=50, mode="market_price_threshold", current_price=0.1,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    def test_market_price_threshold_stays_off_above_threshold(self):
        app = make_app(
            market_price_threshold=0.1,
            current_price_sensor="sensor.current_energy_price",
            current_price_attribute="",
        )
        app.get_state = _entity_states(
            temp=50, mode="market_price_threshold", current_price=0.11,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="off"
        )

    def test_cheapest_hours_runs_during_selected_cheapest_hour(self):
        app = make_app(cheapest_hours_count=1)
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours",
            prices=_sessy_prices(0.30, range(0, 24)) | {"2024-06-15T14:00:00": 0.01},
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    def test_cheapest_hours_stays_off_outside_selected_hour(self):
        app = make_app(cheapest_hours_count=1)
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours",
            prices=_sessy_prices(0.30, range(0, 24)) | {"2024-06-15T13:00:00": 0.01},
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="off"
        )

    def test_unset_mode_defaults_to_economic(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="unknown", prices=_MIDDAY_CHEAP,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="heatpump"
        )

    def test_skips_cycle_when_temp_unavailable(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        app.update_strategy({})
        app.call_service.assert_not_called()


# ===========================================================================
# Economic window helpers
# ===========================================================================

class TestEconomicDecision:
    def test_window_average_ignores_out_of_window_hours(self):
        app = make_app()
        avg = app._window_average(_MIDDAY_CHEAP, 10, 16)
        assert avg == pytest.approx(0.05)

    def test_window_average_none_when_no_entries(self):
        app = make_app()
        assert app._window_average([], 10, 16) is None

    def test_entry_hour_parses_iso_timestamp(self):
        assert BoilerStrategy._entry_hour({"from": "2024-06-15T10:00:00+02:00"}) == 10
        assert BoilerStrategy._entry_hour("2024-06-15T10:00:00") == 10

    def test_entry_hour_none_for_malformed(self):
        assert BoilerStrategy._entry_hour({"from": "not-a-date"}) is None
        assert BoilerStrategy._entry_hour({}) is None
        assert BoilerStrategy._entry_hour("nope") is None

    def test_decision_picks_cheaper_window(self):
        app = make_app()
        # now=8 is outside both windows; day (midday) cheaper → not in window
        in_window, avg1, avg2, chosen = app._cheapest_window_info(8, _MIDDAY_CHEAP)
        assert chosen == "day"
        assert avg1 == pytest.approx(0.05)
        assert avg2 == pytest.approx(0.30)
        assert in_window is False

    def test_decision_heatpump_inside_chosen_window(self):
        app = make_app()
        in_window, _, _, chosen = app._cheapest_window_info(3, _MORNING_CHEAP)
        assert chosen == "night"
        assert in_window is True

    def test_decision_off_without_forecast(self):
        app = make_app()
        in_window, avg1, avg2, chosen = app._cheapest_window_info(14, None)
        assert in_window is False
        assert chosen == "none"
        assert avg1 is None and avg2 is None

    def test_current_price_reads_sensor_state_when_attribute_is_empty(self):
        app = make_app(
            current_price_sensor="sensor.current_energy_price",
            current_price_attribute="",
        )
        app.get_state = MagicMock(return_value="0.08")

        assert app._get_current_price() == pytest.approx(0.08)
        app.get_state.assert_called_once_with("sensor.current_energy_price")

