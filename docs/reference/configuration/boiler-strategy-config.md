# Boiler Strategy Configuration Reference

*Last updated: 2026-09-14 | Part of [Reference Documentation](../../index.md)*

---

## Overview

The Boiler Strategy app (`files/boiler_strategy.py`) is a companion AppDaemon application that controls an Ariston hybrid boiler based on a user-selected strategy mode plus weekly legionella prevention. It runs every 15 minutes and selects the optimal boiler mode to balance energy efficiency with health and safety requirements.

**How changes apply:** AppDaemon automatically reloads apps when `apps.yaml` changes. Configuration parameters take effect on the next scheduled run (within 15 minutes).

**File location:** Typically `/config/appdaemon/apps/apps.yaml`

---

## Configuration Structure

The boiler strategy configuration is organized into logical sections:

1. **Legionella Prevention** — Health and safety temperature thresholds and deadlines
2. **Economic Mode Windows** — Day/night period definitions for cost optimization
3. **Entity IDs** — Home Assistant entity mappings

---

## Complete Configuration Table

| Key | Type | Default | Required | Description | Valid Range | Example |
|-----|------|---------|----------|-------------|-------------|---------|
| **Legionella Prevention** |||||||
| `legionella_temp` | float | 65 | No | Target temperature in °C that the boiler must reach periodically to prevent legionella bacteria growth | > 0 | `65` |
| `legionella_hybrid_days` | float | 6 | No | Days without reaching `legionella_temp` before forcing hybrid mode during cheapest period | > 0 | `6` |
| `legionella_boost_days` | float | 7 | No | Days without reaching `legionella_temp` before forcing boost mode regardless of period | > `legionella_hybrid_days` | `7` |
| **Economic Mode Windows (local hours, [start, end))** |||||||
| `economic_day_start` | int | 10 | No | Start hour of the first economic window (day period) | 0-23 | `10` |
| `economic_day_end` | int | 16 | No | End hour of the first economic window (day period) | 0-23 | `16` |
| `economic_night_start` | int | 0 | No | Start hour of the second economic window (night period) | 0-23 | `0` |
| `economic_night_end` | int | 6 | No | End hour of the second economic window (night period) | 0-23 | `6` |
| `rerun_debounce_s` | float | 2.0 | No | Delay in seconds before re-running after a live input changes. Prevents rapid re-runs during slider drags. | >= 0 | `2.0` |
| **Entity IDs** |||||||
| `temp_sensor` | str | `sensor.boiler_temperatuur` | **Yes** | Boiler water temperature sensor | valid entity ID | `sensor.boiler_temperature` |
| `price_forecast_sensor` | str | `sensor.frankenergy_current_electricity_market_price` | **Yes** | Energy price forecast sensor exposing a `prices` attribute | valid entity ID | `sensor.electricity_price_forecast` |
| `price_forecast_attribute` | str | `prices` | No | Attribute name on `price_forecast_sensor` containing the price list | string | `prices` |
| `mode_select` | str | `input_select.boiler_strategy_mode` | **Yes** | User-selected strategy mode input select | valid entity ID | `input_select.boiler_mode_strategy` |
| `boiler_mode_select` | str | `select.boiler_mode` | **Yes** | Logical actuator for boiler mode (off/heatpump/hybrid/boost/ariston_app) | valid entity ID | `select.boiler_operating_mode` |
| `legionella_last_ok_entity` | str | `input_datetime.boiler_legionella_last_ok` | **Yes** | input_datetime helper that the app stamps whenever the boiler reaches `legionella_temp` | valid entity ID | `input_datetime.boiler_last_legionella_ok` |
| `status_sensor` | str | `sensor.boiler_strategy_status` | **Yes** | Status sensor published by the app with current state and attributes | valid entity ID | `sensor.boiler_strategy_status` |

---

## Configuration Sections Explained

### Legionella Prevention

Legionella bacteria can grow in water systems at temperatures between 20-45°C. Regular heating to 65°C or higher is required to prevent this health risk.

- **`legionella_temp`**: The target temperature in °C. When the boiler reaches or exceeds this temperature, the app records the timestamp in `legionella_last_ok_entity`. Default is 65°C, which is the standard recommendation for legionella prevention.

- **`legionella_hybrid_days`**: The number of days without reaching `legionella_temp` before the app forces hybrid mode. This is a warning stage that runs the boiler in hybrid mode (combining heat pump and electric heating) but only during the cheapest configured period. Default is 6 days.

- **`legionella_boost_days`**: The number of days without reaching `legionella_temp` before the app forces boost mode. This is the final safety stage that runs the boiler in full electric boost mode regardless of cost, ensuring the water is heated to the target temperature. Default is 7 days. Must be greater than `legionella_hybrid_days`.

### Economic Mode Windows

When the user-selected mode is `economic` (the default), the app compares the average forecast price of two configured day/night periods and runs the heat pump only during whichever period is cheaper.

- **Day window** (`economic_day_start` to `economic_day_end`): The first period to evaluate. Default is 10:00-16:00.
- **Night window** (`economic_night_start` to `economic_night_end`): The second period to evaluate. Default is 00:00-06:00.

The app calculates the average price for each window from the price forecast sensor and selects the cheaper window to run the heat pump. Outside the selected window, the boiler stays off.

### Entity IDs

- **`temp_sensor`**: Provides the current boiler water temperature in °C. Required for all operations.

- **`price_forecast_sensor`**: Provides the energy price forecast as a list of entries with `from`, `till`, and `price` fields under the `price_forecast_attribute` (default: `prices`). Used only when mode is `economic`.

- **`price_forecast_attribute`**: The attribute name on `price_forecast_sensor` that contains the forecast price list.

- **`mode_select`**: User input select for choosing the boiler strategy mode. Options: `economic`, `off`, `heatpump`, `hybrid`, `boost`.

- **`boiler_mode_select`**: The actuator entity that the app writes to. The boiler package translates this to the Ariston integration's own `max_temp`.

- **`legionella_last_ok_entity`**: An `input_datetime` helper that the app updates automatically whenever the boiler reaches `legionella_temp`. This tracks when the last successful legionella prevention occurred. The app creates and maintains this entity.

- **`status_sensor`**: A sensor created by the app that exposes the current state and rich attributes including the active branch, temperatures, prices, and days since last legionella prevention.

---

## Configuration Examples

### Minimal Configuration

Only the required entity IDs need to be specified. All other values use sensible defaults.

```yaml
boiler_strategy:
  module: boiler_strategy
  class: BoilerStrategy

  # REQUIRED: Map to your entities
  temp_sensor: sensor.boiler_temperature
  price_forecast_sensor: sensor.electricity_price_forecast
  mode_select: input_select.boiler_strategy_mode
  boiler_mode_select: select.boiler_mode
  legionella_last_ok_entity: input_datetime.boiler_legionella_last_ok
  status_sensor: sensor.boiler_strategy_status
```

### Full Configuration with All Overrides

```yaml
boiler_strategy:
  module: boiler_strategy
  class: BoilerStrategy

  # Legionella prevention
  legionella_temp: 65             # Target temperature for legionella prevention
  legionella_hybrid_days: 6       # Days before hybrid warning triggers
  legionella_boost_days: 7        # Days before boost mode triggers

  # Economic mode windows (local hours)
  economic_day_start: 10
  economic_day_end: 16
  economic_night_start: 0
  economic_night_end: 6

  rerun_debounce_s: 2.0

  # Entity IDs
  temp_sensor: sensor.boiler_temperature
  price_forecast_sensor: sensor.electricity_price_forecast
  price_forecast_attribute: prices
  mode_select: input_select.boiler_strategy_mode
  boiler_mode_select: select.boiler_mode
  legionella_last_ok_entity: input_datetime.boiler_legionella_last_ok
  status_sensor: sensor.boiler_strategy_status
```

---

## Strategy Priority Chain

The boiler strategy evaluates conditions in priority order (first match wins):

| Priority | Condition | Action | Mode Override |
|----------|-----------|--------|---------------|
| **P1** | Days since last `legionella_temp` >= `legionella_boost_days` AND mode != `off` | Force mode `boost` | Always |
| **P2** | User selected `off`, `heatpump`, `hybrid`, or `boost` | Force that mode directly | Always |
| **P3** | Mode is `economic` AND days since last `legionella_temp` >= `legionella_hybrid_days` | Force mode `hybrid` | Only during cheapest window |
| **P4** | Mode is `economic` | Run heat pump during cheaper of the two configured windows; off otherwise | N/A |

---

## Legionella Tracking

The app automatically tracks when the boiler reaches the target temperature:

1. Every cycle (15 minutes), the app reads the current temperature from `temp_sensor`.
2. If `temp >= legionella_temp`, the app stamps the current datetime to `legionella_last_ok_entity`.
3. The `_days_since_legionella_ok()` method calculates: `(now - last_ok_timestamp) / 86400 seconds`.
4. This value is compared against `legionella_hybrid_days` and `legionella_boost_days` to trigger prevention actions.

!!! note
    If `legionella_last_ok_entity` has never been set (fresh install), the app assumes the value is already at the `legionella_hybrid_days` threshold. This escalates to hybrid mode but stops short of forcing a boost on first run.

---

## Price Forecast Format

The `price_forecast_sensor` must expose a list of price entries under the configured attribute. Each entry should have:

- `from`: ISO 8601 datetime string for the start of the period
- `till`: ISO 8601 datetime string for the end of the period  
- `price`: Numeric price value in €/kWh

Example format:

```yaml
prices:
  - from: "2026-09-14T00:00:00+02:00"
    till: "2026-09-14T01:00:00+02:00"
    price: 0.254
  - from: "2026-09-14T01:00:00+02:00"
    till: "2026-09-14T02:00:00+02:00"
    price: 0.189
  # ... more entries
```

The app uses the `from` field's hour component to determine which window each price belongs to.

---

## Validation Rules

1. **Required entities**: `temp_sensor`, `price_forecast_sensor`, `mode_select`, `boiler_mode_select`, `legionella_last_ok_entity`, `status_sensor` must be valid entity IDs in your Home Assistant.

2. **Positive values**: `legionella_temp`, `legionella_hybrid_days`, `legionella_boost_days`, `rerun_debounce_s` must be > 0.

3. **Window ordering**: `economic_day_start` < `economic_day_end`, `economic_night_start` < `economic_night_end`.

4. **Threshold ordering**: `legionella_boost_days` must be > `legionella_hybrid_days` for proper escalation.

5. **Time values**: All hour values (economic window start/end) must be in range 0-23.

---

## Tips

1. **Start with defaults**: The default values work well for most installations with weekly legionella prevention cycles.

2. **Adjust windows to match your usage**: If your energy prices follow a different pattern, adjust the `economic_day_*` and `economic_night_*` windows to match your cheaper and more expensive periods.

3. **Legionella thresholds**: If local regulations require different legionella prevention intervals, adjust `legionella_hybrid_days` and `legionella_boost_days` accordingly. The 6/7 day defaults follow common European guidelines.

4. **Temperature threshold**: If your boiler or local health authority specifies a different temperature for legionella prevention, adjust `legionella_temp`. 65°C is the standard, but some jurisdictions may require 60°C or 70°C.

5. **Verify entity IDs**: Use Home Assistant's **Developer Tools → States** to confirm your entity IDs before configuring. The defaults are examples from the author's installation.

6. **Create the legionella tracking entity**: Before starting the app, create an `input_datetime` entity in Home Assistant (Settings → Devices & Services → Helpers) and note its entity ID for the `legionella_last_ok_entity` configuration. The app will update this automatically.

---

## See Also

- [Entity Reference](../entity-reference.md) — All entities used and created by the app
- [Boiler Strategy Priority Chain](../../explanation/boiler-strategy-priority-chain.md) — Detailed explanation of decision logic
- [apps.yaml Configuration](apps-yaml.md) — Main SessyStrategy configuration reference
- [Live Tuning Entities](../live-tuning-entities.md) — Runtime-adjustable helpers
- [Status Sensor Attributes](../status-sensor-attributes.md) — Attributes exposed by the status sensor
