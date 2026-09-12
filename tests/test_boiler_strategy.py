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
    economic_window1_start=10,
    economic_window1_end=16,
    economic_window2_start=0,
    economic_window2_end=6,
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

def _price_entry(hour, price):
    return {
        "from": f"2024-06-15T{hour:02d}:00:00+02:00",
        "till": f"2024-06-15T{hour + 1:02d}:00:00+02:00",
        "price": price,
    }


def _entity_states(temp, mode="economic", prices=None, legionella_last_ok=None,
                   boiler_mode="init"):
    states = {
        "sensor.boiler_temperatuur": str(temp),
        "input_select.boiler_strategy_mode": mode,
        "input_datetime.boiler_legionella_last_ok": legionella_last_ok,
        "select.boiler_mode": boiler_mode,
        "sensor.boiler_strategy_status": "ok",
    }

    def _get_state(entity_id=None, attribute=None):
        if entity_id == "sensor.frankenergy_current_electricity_market_price" and attribute == "prices":
            return prices
        return states.get(entity_id)

    return _get_state


# Cheaper morning window (0-6) vs pricier midday window (10-16).
_MORNING_CHEAP = [_price_entry(h, 0.05) for h in range(0, 6)] + \
                 [_price_entry(h, 0.30) for h in range(10, 16)]
# Cheaper midday window (10-16) vs pricier morning window (0-6).
_MIDDAY_CHEAP = [_price_entry(h, 0.30) for h in range(0, 6)] + \
                [_price_entry(h, 0.05) for h in range(10, 16)]


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

    def test_entry_hour_none_for_malformed(self):
        assert BoilerStrategy._entry_hour({"from": "not-a-date"}) is None
        assert BoilerStrategy._entry_hour({}) is None
        assert BoilerStrategy._entry_hour("nope") is None

    def test_decision_picks_cheaper_window(self):
        app = make_app()
        # now=8 is outside both windows; midday cheaper → mode off (not in window)
        mode, avg1, avg2, chosen = app._economic_decision(8, _MIDDAY_CHEAP)
        assert chosen == "day"
        assert avg1 == pytest.approx(0.05)
        assert avg2 == pytest.approx(0.30)
        assert mode == "off"

    def test_decision_heatpump_inside_chosen_window(self):
        app = make_app()
        mode, _, _, chosen = app._economic_decision(3, _MORNING_CHEAP)
        assert chosen == "night"
        assert mode == "heatpump"

    def test_decision_off_without_forecast(self):
        app = make_app()
        mode, avg1, avg2, chosen = app._economic_decision(14, None)
        assert mode == "off"
        assert chosen is None
        assert avg1 is None and avg2 is None

