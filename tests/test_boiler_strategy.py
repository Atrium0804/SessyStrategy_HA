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


def _entity_states(temp, mode="cheapest_hours", prices=None, legionella_last_ok=None,
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


# 14:00 is the single cheapest hour of the 2024-06-15 window.
_CHEAP_AT_14 = {**_sessy_prices(0.30, range(24)), "2024-06-15T14:00:00": 0.01}


class TestUpdateStrategyPriority:
    # ── Legionella boost overrides any user mode except 'off' ────────────────
    def test_legionella_boost_forces_boost_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours",
            legionella_last_ok="2024-06-07 14:00:00",  # 8 days ago
        )
        app.update_strategy({})
        app.call_service.assert_any_call(
            "select/select_option", entity_id="select.boiler_mode", option="boost"
        )

    def test_legionella_hybrid_warning_forces_hybrid_mode(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours", prices=_CHEAP_AT_14,
            legionella_last_ok="2024-06-09 14:00:00",  # 6 days ago; clock=14:00 is the cheapest hour
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

    def test_boost_not_resent_when_already_boost(self):
        # Re-sending boost restarts the Ariston boost/heat pump every cycle.
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="boost", legionella_last_ok="2024-06-14 14:00:00",
            boiler_mode="boost",
        )
        app.update_strategy({})
        assert not any(
            c.args and c.args[0] == "select/select_option"
            for c in app.call_service.call_args_list
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

    @pytest.mark.parametrize("last_ok, branch", [
        ("2024-06-14 14:00:00", "cheapest_hours_heatpump"),
        ("2024-06-09 14:00:00", "legionella_hybrid"),
        ("2024-06-07 14:00:00", "legionella_boost"),
    ])
    def test_cheapest_threshold_published_even_during_legionella_override(self, last_ok, branch):
        app = make_app(cheapest_hours_count=2, cheapest_window_start_h=2)
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours",
            prices=_sessy_prices(0.30, range(24)) | {
                "2024-06-15T14:00:00": 0.01,
                "2024-06-16T00:00:00": 0.02,
            },
            legionella_last_ok=last_ok,
        )
        app.update_strategy({})
        status = app.set_state.call_args.kwargs
        assert status["state"] == branch
        assert status["attributes"]["cheapest_hours_price_threshold"] == 0.02
        assert status["attributes"]["cheapest_hours_window_start"] == "2024-06-15T02:00:00"
        assert status["attributes"]["cheapest_hours_window_end"] == "2024-06-16T02:00:00"

    def test_cheapest_threshold_updates_with_live_count_and_clears_on_mode_change(self):
        app = make_app(cheapest_hours_count=1)
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours",
            prices=_sessy_prices(0.30, range(24)) | {"2024-06-15T14:00:00": 0.01},
            legionella_last_ok="2024-06-14 14:00:00",
        )
        original_get_state = app.get_state
        app.get_state = lambda entity_id=None, attribute=None: (
            "2" if entity_id == app.cheapest_hours_count_entity
            else original_get_state(entity_id, attribute)
        )
        app.update_strategy({})
        assert app.set_state.call_args.kwargs["attributes"]["cheapest_hours_price_threshold"] == 0.30
        app.get_state = _entity_states(temp=50, mode="off")
        app.update_strategy({})
        attributes = app.set_state.call_args.kwargs["attributes"]
        assert attributes["cheapest_hours_price_threshold"] is None
        assert attributes["cheapest_hours_window_start"] is None
        assert attributes["cheapest_hours_window_end"] is None

    def test_cheapest_threshold_is_none_without_forecast(self):
        app = make_app()
        app.get_state = _entity_states(
            temp=50, mode="cheapest_hours", prices=None,
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        assert app.set_state.call_args.kwargs["attributes"]["cheapest_hours_price_threshold"] is None

    @pytest.mark.parametrize("raw_mode", ["unknown", "economic"])
    def test_unset_or_retired_mode_runs_cheapest_hours(self, raw_mode):
        app = make_app(cheapest_hours_count=1)
        app.get_state = _entity_states(
            temp=50, mode=raw_mode,
            prices=_sessy_prices(0.30, range(24)) | {"2024-06-15T14:00:00": 0.01},
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        assert app.set_state.call_args.kwargs["state"] == "cheapest_hours_heatpump"

    def test_skips_cycle_when_temp_unavailable(self):
        app = make_app()
        app.get_state = MagicMock(return_value=None)
        app.update_strategy({})
        app.call_service.assert_not_called()


# ===========================================================================
# Price readers
# ===========================================================================

class TestPriceReaders:
    def test_current_price_comes_from_shared_price_data_with_utc_keys(self):
        # 14:00 CEST = 12:00 UTC; the fallback sensor must not be used.
        app = make_app(market_price_threshold=0.1, current_price_sensor="sensor.current_energy_price")
        app.get_state = _entity_states(
            temp=50, mode="market_price_threshold", current_price=0.50,
            prices={"2024-06-15T12:00:00+00:00": 0.05, "2024-06-15T13:00:00+00:00": 0.40},
            legionella_last_ok="2024-06-14 14:00:00",
        )
        app.update_strategy({})
        attributes = app.set_state.call_args.kwargs["attributes"]
        assert app.set_state.call_args.kwargs["state"] == "market_price_heatpump"
        assert attributes["current_price"] == "0.05"
    def test_current_price_reads_sensor_state_when_attribute_is_empty(self):
        app = make_app(
            current_price_sensor="sensor.current_energy_price",
            current_price_attribute="",
        )
        app.get_state = MagicMock(return_value="0.08")

        assert app._get_current_price() == pytest.approx(0.08)
        app.get_state.assert_called_once_with("sensor.current_energy_price")

