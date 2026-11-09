# Boiler Strategy Configuration Reference

*Last updated: 2026-11-09 | Part of [Reference Documentation](../../index.md)*

---

## Overview

The Boiler Strategy app (`files/boiler_strategy.py`) is a companion AppDaemon application that controls an Ariston hybrid boiler based on a user-selected strategy mode plus weekly legionella prevention. It runs every 15 minutes and selects the optimal boiler mode to balance energy efficiency with health and safety requirements.

**How changes apply:** AppDaemon automatically reloads apps when `apps.yaml` changes. Configuration parameters take effect on the next scheduled run (within 15 minutes).

**File location:** Typically `/config/appdaemon/apps/apps.yaml`

---

## Configuration Structure

The boiler strategy configuration is organized into logical sections:

1. **Legionella Prevention** — Health and safety temperature thresholds and deadlines
2. **Price-Based Strategies** — Market price threshold and cheapest hours (shared price window)
3. **Entity IDs** — Home Assistant entity mappings

---

## Complete Configuration Table

| Key | Type | Default | Required | Description | Valid Range | Example |
|-----|------|---------|----------|-------------|-------------|---------|
| **Legionella Prevention** |||||||
| `legionella_temp` | float | 65 | No | Target temperature in °C that the boiler must reach periodically to prevent legionella bacteria growth | > 0 | `65` |
| `legionella_hybrid_days` | float | 6 | No | Days without reaching `legionella_temp` before forcing hybrid mode during cheapest period | > 0 | `6` |
| `legionella_boost_days` | float | 7 | No | Days without reaching `legionella_temp` before forcing boost mode regardless of period | > `legionella_hybrid_days` | `7` |
| **Price-Based Strategies** |||||||
| `market_price_threshold` | float | 0.1 | No | Maximum current price in €/kWh at which to run the heat pump | >= 0 | `0.1` |
| `cheapest_hours_count` | int | 1 | No | Run the heat pump when the current hour ranks within the N cheapest of the 24h price window (same ranking as the battery) | 1-24 | `3` |
| `cheapest_window_start_h` | int | 2 | No | Start hour of the 24h window (02:00 to 02:00), shared with the battery. In `apps.yaml` set it with the alias `*cheapest_window_start_h` so both apps use the same value | 0-23 | `*cheapest_window_start_h` |
| `rerun_debounce_s` | float | 2.0 | No | Delay in seconds before re-running after a live input changes. Prevents rapid re-runs during slider drags. | >= 0 | `2.0` |
| **Entity IDs** |||||||
| `temp_sensor` | str | `sensor.boiler_temperatuur` | **Yes** | Boiler water temperature sensor | valid entity ID | `sensor.boiler_temperature` |
| `price_forecast_sensor` | str | `sensor.sessy_dnhh_energy_price` | **Yes** | Sessy energy price sensor exposing an `energy_prices` dict (same sensor as the battery) | valid entity ID | `sensor.sessy_dnhh_energy_price` |
| `price_forecast_attribute` | str | `energy_prices` | No | Attribute name on `price_forecast_sensor` containing the `{timestamp: price}` dict | string | `energy_prices` |
| `current_price_sensor` | str | `sensor.current_energy_price` | No | Fallback current-price sensor for `market_price_threshold`, used only when the shared price data has no price for the current hour | valid entity ID | `sensor.sessy_dnhh_energy_price` |
| `current_price_attribute` | str | `price` | No | Attribute containing the fallback current price; use an empty string when the sensor state is the price | string or empty | `""` |
| `mode_select` | str | `input_select.boiler_strategy_mode` | **Yes** | User-selected strategy mode input select (`off`, `heatpump`, `hybrid`, `boost`, `market_price_threshold`, `cheapest_hours`) | valid entity ID | `input_select.boiler_mode_strategy` |
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

### Price-Based Strategies

The default mode is `cheapest_hours`. An unset mode, or a leftover `economic` selection (that mode is retired), runs as `cheapest_hours`; the app also switches `mode_select` to `cheapest_hours` and logs a WARNING.

- **`cheapest_hours`**: Runs the heat pump when the current hour ranks within the N cheapest (`cheapest_hours_count`) of the 24h price window from `cheapest_window_start_h` (default 02:00 → 02:00). `files/cheapest_hours.py` does this ranking for both the battery and the boiler, so both use the identical window. Only N differs: `cheapest_hours_n` (battery) versus `cheapest_hours_count` (boiler).
- **`market_price_threshold`**: Runs the heat pump when the current price is at or below `market_price_threshold`. The current price is the current local hour's price from the shared price data (`price_forecast_sensor`). `current_price_sensor` / `current_price_attribute` are only a fallback when that data has no price for the current hour.

### Entity IDs

- **`temp_sensor`**: Provides the current boiler water temperature in °C. Required for all operations.

- **`price_forecast_sensor`**: The Sessy energy price sensor. Provides a dict of `{ISO_timestamp: price}` under the `price_forecast_attribute` (default: `energy_prices`). See [Price Forecast Format](#price-forecast-format).

- **`price_forecast_attribute`**: The attribute name on `price_forecast_sensor` that contains the price dict.

- **`mode_select`**: User input select for choosing the boiler strategy mode. Options: `cheapest_hours`, `market_price_threshold`, `off`, `heatpump`, `hybrid`, `boost`.

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
  price_forecast_sensor: sensor.sessy_dnhh_energy_price
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

  # Price-based strategies
  market_price_threshold: 0.1
  cheapest_hours_count: 1
  cheapest_window_start_h: *cheapest_window_start_h   # Alias of the anchor in sessy_strategy

  rerun_debounce_s: 2.0

  # Entity IDs
  temp_sensor: sensor.boiler_temperature
  price_forecast_sensor: sensor.sessy_dnhh_energy_price
  price_forecast_attribute: energy_prices
  current_price_sensor: sensor.sessy_dnhh_energy_price   # Fallback only
  current_price_attribute: ""
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
| **P3** | Mode is `market_price_threshold` or `cheapest_hours` AND days since last `legionella_temp` >= `legionella_hybrid_days` | Force mode `hybrid` | Only during the mode's cheapest period |
| **P4** | Mode is `market_price_threshold` | Run heat pump when current price <= `market_price_threshold`; off otherwise | N/A |
| **P5** | Mode is `cheapest_hours` (default) | Run heat pump during the N cheapest hours of the shared price window; off otherwise | N/A |

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

The `price_forecast_sensor` must expose the Sessy format: a dict of `{ISO_timestamp: price}` under the configured attribute (default `energy_prices`). Keys are UTC with an offset; prices are in €/kWh.

Example format:

```yaml
energy_prices:
  '2026-11-09T16:00:00+00:00': 0.60945   # = 17:00 CET
  '2026-11-09T17:00:00+00:00': 0.52310   # = 18:00 CET
  # ... more entries
```

`files/cheapest_hours.py` converts each key to the AppDaemon local timezone and averages the slots per local clock hour. Keys without an offset are read as local time. The same reader serves the battery and the boiler.

!!! warning
    The Frank Energie format (a list of `{from, till, price}` entries) is no longer supported.

---

## Validation Rules

1. **Required entities**: `temp_sensor`, `price_forecast_sensor`, `mode_select`, `boiler_mode_select`, `legionella_last_ok_entity`, `status_sensor` must be valid entity IDs in your Home Assistant.

2. **Positive values**: `legionella_temp`, `legionella_hybrid_days`, `legionella_boost_days`, `rerun_debounce_s` must be > 0.

3. **Window start**: `cheapest_window_start_h` must equal the battery's value; use the `*cheapest_window_start_h` alias in `apps.yaml`.

4. **Threshold ordering**: `legionella_boost_days` must be > `legionella_hybrid_days` for proper escalation.

5. **Time values**: `cheapest_window_start_h` must be in range 0-23.

---

## Migration from `economic` mode

The `economic` mode is retired. Use `cheapest_hours` (default) or `market_price_threshold` instead.

1. Remove all `economic_*` keys from the `boiler_strategy` section in `apps.yaml`.
2. Remove `economic` from the `input_select.boiler_strategy_mode` options; set `initial: cheapest_hours`.
3. Switch `price_forecast_sensor` to the Sessy sensor (`energy_prices`); the Frank Energie format is dropped.

A leftover `economic` selection runs as `cheapest_hours`, and the app switches the `input_select` to `cheapest_hours` (WARNING in the log). See [Set Up Boiler Strategy](../../how-to/setup-boiler-strategy.md#migrating-from-the-economic-mode).

---

## Tips

1. **Start with defaults**: The default values work well for most installations with weekly legionella prevention cycles.

2. **Tune N, not the window**: Change `cheapest_hours_count` (or the live `input_number.boiler_cheapest_hours_count`) to run the heat pump longer or shorter. Change `cheapest_window_start_h` only together with the battery, through the shared anchor.

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
