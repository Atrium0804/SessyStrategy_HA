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
    setpoint_c=60,
    soc_full_threshold=95,
    gas_price=1.50,
    boiler_efficiency=95,
    cop=2.0,
    calorific_value=9.77,
    legionella_temp=65,
    legionella_hybrid_days=6,
    legionella_boost_days=7,
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

def _entity_states(temp, buy_price, sell_price, soc, legionella_last_ok=None, mode="init", setpoint="55"):
    states = {
        "sensor.boiler_temperature": str(temp),
        "sensor.energy_buy_price": str(buy_price),
        "sensor.energy_sell_price": str(sell_price),
        "sensor.sessy_battery_alt9_state_of_charge": str(soc),
        "input_datetime.boiler_legionella_last_ok": legionella_last_ok,
        "select.boiler_modus": mode,
        "number.boiler_setpoint": setpoint,
        "sensor.boiler_strategy_status": "ok",
    }

    def _get_state(entity_id=None, attribute=None):
        return states.get(entity_id)

    return _get_state


class TestUpdateStrategyPriority:
    def test_legionella_boost_forces_boost_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, buy_price=0.20, sell_price=0.15, soc=50,
            legionella_last_ok="2024-06-07 14:00:00",  # 8 days ago
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_modus", option="boost"
        )
        app.call_service.assert_any_call(
            "number/set_value", entity_id="number.boiler_setpoint", value=65.0
        )

    def test_legionella_hybrid_warning_forces_hybrid_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, buy_price=0.20, sell_price=0.15, soc=50,
            legionella_last_ok="2024-06-09 14:00:00",  # 6 days ago
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_modus", option="hybrid"
        )
        app.call_service.assert_any_call(
            "number/set_value", entity_id="number.boiler_setpoint", value=60.0
        )

    def test_price_off_when_expensive_and_battery_not_full(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, buy_price=5.0, sell_price=5.0, soc=50,
            legionella_last_ok="2024-06-14 14:00:00",  # 1 day ago
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_modus", option="off"
        )

    def test_price_heatpump_when_cheap(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, buy_price=-0.5, sell_price=-0.5, soc=50,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_modus", option="heatpump"
        )

    def test_price_hybrid_when_soc_full_and_cheap(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, buy_price=5.0, sell_price=-0.5, soc=99,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_modus", option="hybrid"
        )

    def test_skips_cycle_when_sensor_unavailable(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        app.update_strategy({})
        app.call_service.assert_not_called()
