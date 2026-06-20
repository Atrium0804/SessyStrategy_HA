# Running the tests

This guide is for contributors who have never run Python tests before.

## What the tests do

The tests verify that `sessy_strategy.py` makes the right decisions — charging
when prices are cheap, discharging when they are high, and sitting at 0 W
otherwise. They also check that individual calculations (watts to charge,
watts to discharge, etc.) produce the correct numbers.

Home Assistant and AppDaemon are **not needed** to run the tests. A lightweight
stub replaces them so the tests run entirely on your laptop.

---

## Prerequisites

You need **Python 3.10 or later**. Check your version:

```
python --version
```

---

## Install the test tools

From the root of this repository, run:

```
pip install -r requirements-dev.txt
```

This installs [pytest](https://docs.pytest.org/), the test framework used here.
You only need to do this once.

---

## Run all tests

```
pytest
```

Pytest finds and runs every test in `tests/` automatically. A clean run looks
like:

```
collected 50 items

tests/test_sessy_strategy.py ..................................................  [100%]

50 passed in 0.15s
```

---

## Run a subset of tests

Run a single test class:

```
pytest tests/test_sessy_strategy.py::TestChargeSetpoint
```

Run a single test function:

```
pytest tests/test_sessy_strategy.py::TestChargeSetpoint::test_basic_gap
```

Run all tests whose name contains a word:

```
pytest -k discharge
```

---

## Understanding the output

| Symbol | Meaning |
|--------|---------|
| `.`    | Test passed |
| `F`    | Test failed — the result did not match what was expected |
| `E`    | Error — the test itself crashed (e.g. a missing import) |

When a test fails, pytest prints the exact line and the values that did not
match. For example:

```
FAILED tests/test_sessy_strategy.py::TestChargeSetpoint::test_basic_gap
AssertionError: assert 800.0 == approx(1000.0 ± 1.0e-06)
```

This tells you the method returned `800.0` but the test expected `1000.0`.

---

## How the tests are structured

All tests live in [`tests/test_sessy_strategy.py`](tests/test_sessy_strategy.py).

| Test class | What it covers |
|---|---|
| `TestChargeSetpoint` | Watt calculation for pre-peak charging |
| `TestDischargeSetpoint` | Watt calculation for price-spike discharge |
| `TestCheapChargeSetpoint` | Watt calculation during cheap / negative prices |
| `TestPostPeakDischargeSetpoint` | Watt calculation for post-peak excess drain |
| `TestSeasonalValue` | Winter override selection |
| `TestActiveSeasonMode` | Season auto-detection from the daily price minimum |
| `TestTunable` | Live `input_number` helper resolution |
| `TestEnableSwitch` | Master on/off switch behaviour |
| `TestSensorReaders` | Reading SOC, price, and price-window data from HA |
| `TestPublishStatus` | Status sensor attribute publishing |
| `TestUpdateStrategyBranches` | Full decision chain (all four priorities) |

---

## How the HA stub works

AppDaemon normally injects `hass.Hass` at runtime inside Home Assistant. The
tests replace it with a small fake class before importing `sessy_strategy.py`.
That means `get_state`, `call_service`, `set_state`, and `log` are all
`MagicMock` objects — you can tell them what to return and later check how
they were called.

The `make_app()` factory at the top of the test file creates a ready-to-use
`SessyStrategy` instance with all HA calls mocked and sensible defaults loaded
from `apps.yaml`.

---

## Adding a new test

1. Open [`tests/test_sessy_strategy.py`](tests/test_sessy_strategy.py).
2. Find the class that matches what you want to test (or add a new class at
   the bottom).
3. Write a method whose name starts with `test_`.

A minimal example — testing that a very small charge gap still returns the
50 W minimum:

```python
def test_minimum_50w(self):
    app = make_app()
    # Gap: (90-89)/100 * 5000 Wh / 2 h = 25 W → floor at 50 W
    result = app._charge_setpoint(soc=89, soc_target=90, prepeak_window_h=2.0)
    assert result == pytest.approx(50.0)
```

An example that checks a full strategy decision — mocking the sensors:

```python
def test_high_price_triggers_discharge(self):
    app = make_app()
    app._get_soc = MagicMock(return_value=80.0)
    app._get_current_price = MagicMock(return_value=0.45)   # above price_discharge
    app._publish_status = MagicMock()
    app._set_battery_setpoint = MagicMock()
    app._set_grid_setpoint = MagicMock()
    app._get_prices_dict = MagicMock(return_value=None)

    app.update_strategy({})

    app._set_battery_setpoint.assert_called_once()
    assert app._set_battery_setpoint.call_args[0][0] > 0   # positive = discharge
```

Run `pytest` after adding your test to confirm it passes.
