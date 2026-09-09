# Configuration Reference — apps.yaml

*Last updated: 2026-08-01 | Part of [Reference Documentation](../../index.md)*

---

## Overview

The SessyStrategy AppDaemon app is configured entirely through `apps.yaml`. All tunables, entity IDs, and operational parameters are defined as app arguments. **No code editing is required** — simply modify values in your `apps.yaml` file and restart AppDaemon (or wait for auto-reload).

**How changes apply:** AppDaemon automatically reloads apps when `apps.yaml` changes. For live-tunable parameters (those with `_entity` suffixes), changes take effect immediately without any restart.

**File location:** Typically `/config/appdaemon/apps/apps.yaml`

---

## Configuration Structure

The configuration is organized into logical sections:

1. **Battery / Hardware** — Physical battery specifications
2. **State-of-Charge Targets** — SOC management thresholds
3. **Pricing** — Energy price thresholds and surcharges
4. **Adaptive Spread Window** — Dynamic power distribution settings
5. **Time Windows** — Operational time periods
6. **Entity IDs** — Home Assistant entity mappings
7. **Operating Mode** — Master control and mode selection
8. **Live Tuning** — Optional runtime-adjustable helpers

---

## Complete Configuration Table

| Key | Type | Default | Required | Description | Valid Range | Example |
|-----|------|---------|----------|-------------|-------------|---------|
| **Battery / Hardware** |||||||
| `capacity_wh` | float | 5000 | Yes | Battery capacity in watt-hours | > 0 | `5000` |
| `max_power_w` | float | 2200 | Yes | Maximum inverter/battery power in watts — final setpoint clamp | > 0 | `2200` |
| **State-of-Charge Targets** |||||||
| `target_afternoon_charging` | float | 70 | No | Target SOC to reach before the evening peak (P3) | 0-100 | `70` |
| `target_peak_discharge` | float | 70 | No | SOC above which evening excess is sold (P4) | 0-100 | `70` |
| `target_morning_soc` | float | 30 | No | SOC to unload down to in the morning window (P5) | 0-100 | `30` |
| `soc_floor` | float | 0 | No | SOC floor percentage — battery never discharges below this | 0-100 | `20` |
| `cheap_soc_target` | float | 100 | No | SOC ceiling for cheap-price charging | 0-100 | `100` |
| **Pricing** |||||||
| `surcharge` | float | 0.11 | No | Import surcharge €/kWh (raw export → import price conversion) | ≥ 0 | `0.11` |
| `price_discharge` | float | 0.39 | No | Raw price threshold above which to force discharge | any | `0.39` |
| `price_charge` | float | -0.10 | No | Raw price threshold below which to charge from grid | any | `-0.10` |
| `min_arbitrage_margin` | float | 0.05 | No | Minimum €/kWh spread for the evening peak hold-vs-sell decision (P4) | ≥ 0 | `0.05` |
| `afternoon_margin` | float | 0.05 | No | Minimum €/kWh by which the evening peak import price must beat the current import price to justify afternoon charge (P3) | ≥ 0 | `0.05` |
| **Adaptive Spread Window** |||||||
| `min_window_h` | float | 2.0 | No | Minimum adaptive spread window in hours | > 0 | `2.0` |
| `rerun_debounce_s` | float | 2.0 | No | Delay in seconds before re-running after live input changes | ≥ 0 | `2.0` |
| **Time Windows (local hours)** |||||||
| `afternoon_start` | int | 16 | No | Start hour of afternoon charge window | 0-23 | `16` |
| `afternoon_end` | int | 18 | No | End hour of afternoon charge window | 0-23 | `18` |
| `afternoon_window_h` | float | 2.0 | No | Spread window for afternoon charge in hours | > 0 | `2.0` |
| `evening_peak_start` | int | 20 | No | Start hour of evening peak window | 0-23 | `20` |
| `evening_peak_end` | int | 22 | No | End hour of evening peak window | 0-23 | `22` |
| **Entity IDs** |||||||
| `strategy_select` | str | "select.sessy_battery_alt9_power_strategy" | **Yes** | Sessy strategy selector entity | valid entity ID | `select.sessy_battery_<id>_power_strategy` |
| `grid_target` | str | "number.sessy_pwkn_grid_target" | **Yes** | Grid power target entity | valid entity ID | `number.sessy_<id>_grid_target` |
| `battery_setpoint` | str | "number.sessy_battery_alt9_power_setpoint" | **Yes** | Battery power setpoint entity | valid entity ID | `number.sessy_battery_<id>_power_setpoint` |
| `soc_sensor` | str | "sensor.sessy_battery_alt9_state_of_charge" | **Yes** | Current SOC sensor entity | valid entity ID | `sensor.sessy_battery_<id>_state_of_charge` |
| `price_sensor` | str | "sensor.sessy_dnhh_energy_price" | **Yes** | Current energy price sensor entity | valid entity ID | `sensor.sessy_<id>_energy_price` |
| `status_sensor` | str | "sensor.sessy_strategy_status" | **Yes** | Status sensor published by the app | valid entity ID | `sensor.sessy_strategy_status` |
| **Operating Mode** |||||||
| `mode_select` | str | null | No | Master mode selector | valid entity ID | `select.home_battery_mode` |
| `setpoint_entity` | str | null | No | Manual setpoint entity for grid/battery modes | valid entity ID | `number.home_battery_setpoint` |
| `sessy_dynamic_option` | str | "roi" | No | Sessy power_strategy option for "Sessy dynamic" mode | valid option string | `roi` |
| `eco_option` | str | "eco" | No | Sessy power_strategy option for "Eco" mode | valid option string | `eco` |
| `idle_option` | str | "idle" | No | Sessy power_strategy option for "Idle" mode | valid option string | `idle` |
| **Live Tuning Helpers** |||||||
| `target_afternoon_charging_entity` | str | null | No | Live afternoon SOC target override, P3 (input_number) | valid entity ID | `number.home_battery_target_afternoon_charging` |
| `target_peak_discharge_entity` | str | null | No | Live evening peak sell-off target override, P4 (input_number) | valid entity ID | `number.home_battery_target_peak_discharge` |
| `target_morning_soc_entity` | str | null | No | Live morning sell-off target override, P5 (input_number) | valid entity ID | `number.home_battery_target_morning_soc` |
| `soc_floor_entity` | str | null | No | Live SOC floor override (input_number) | valid entity ID | `number.home_battery_soc_floor` |
| `cheap_soc_target_entity` | str | null | No | Live cheap SOC target override (input_number) | valid entity ID | `number.home_battery_soc_ceiling` |
| `price_discharge_entity` | str | null | No | Live discharge threshold override (input_number) | valid entity ID | `number.home_battery_price_discharge` |
| `price_charge_entity` | str | null | No | Live charge threshold override (input_number) | valid entity ID | `number.home_battery_price_charge` |
| `min_arbitrage_margin_entity` | str | null | No | Live arbitrage margin override, P4 (input_number) | valid entity ID | `number.home_battery_min_arbitrage_margin` |
| `afternoon_margin_entity` | str | null | No | Live afternoon margin override (input_number) | valid entity ID | `number.home_battery_afternoon_margin` |

---

## Configuration Sections Explained

### Battery / Hardware

These define the physical capabilities of your battery system.

- **`capacity_wh`**: Total energy storage capacity. Used to calculate charge/discharge amounts based on SOC percentages.
- **`max_power_w`**: Maximum power the inverter can handle. All setpoints are clamped to this value.

### State-of-Charge Targets

These control how the battery is charged and discharged.

- **`target_afternoon_charging`**: The target SOC to reach before the evening peak. Used in Priority 3 (afternoon charge).
- **`target_peak_discharge`**: The SOC above which the evening peak sell-off (Priority 4) discharges surplus energy.
- **`target_morning_soc`**: The SOC to unload down to during the morning sell-off window (Priority 5).
- **`soc_floor`**: The minimum SOC level. The battery will never discharge below this percentage.
- **`cheap_soc_target`**: The target SOC for cheap-price charging (Priority 2). Typically set to 100% to fully charge during cheap hours.

### Pricing

Price-related configuration uses **raw export prices** (what the grid pays you), not import prices.

- **`surcharge`**: The tax/fee added to raw prices to get import prices. Default €0.11/kWh for Dutch energy tax.
- **`price_discharge`**: When raw price exceeds this, Priority 1 (price-spike discharge) triggers.
- **`price_charge`**: When raw price is below this (typically negative), Priority 2 (cheap charge) triggers.
- **`min_arbitrage_margin`**: Minimum price spread required for Priority 4 (evening peak hold-vs-sell decision).
- **`afternoon_margin`**: Minimum amount (€/kWh) by which the evening peak import price must beat the current import price for Priority 3 (afternoon charge) to top up. This is a peak-shaving check to avoid net grid import at the evening peak, not a trading margin.

**Important**: All price thresholds are in **raw export prices**. The import equivalent is `raw_price + surcharge`.

### Adaptive Spread Window

- **`min_window_h`**: Minimum window for spreading charge/discharge power. Prevents excessively high power draws.
- **`rerun_debounce_s`**: Delay before re-running strategy after a live input changes. Prevents rapid re-runs during slider drags.

### Time Windows

All times are in **local hours** (24-hour format).

- **Afternoon window** (`afternoon_start` to `afternoon_end`): When to top up in preparation for the evening peak.
- **Evening peak window** (`evening_peak_start` to `evening_peak_end`): Evening peak period for Priority 4 (excess discharge).

---

## Configuration Examples

### Minimal Configuration

Only the required entity IDs need to be specified. All other values use sensible defaults.

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  # Required: map to your Sessy entities
  strategy_select: select.sessy_battery_myid_power_strategy
  grid_target: number.sessy_myid_grid_target
  battery_setpoint: number.sessy_battery_myid_power_setpoint
  soc_sensor: sensor.sessy_battery_myid_state_of_charge
  price_sensor: sensor.sessy_myid_energy_price
  status_sensor: sensor.sessy_strategy_status
```

### Full Configuration with All Overrides

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  # Battery / hardware
  capacity_wh: 10000          # 10 kWh battery
  max_power_w: 3500          # 3.5 kW inverter

  # SOC targets
  target_afternoon_charging: 80   # Target 80% before evening peak
  target_peak_discharge: 80       # Sell evening excess above 80%
  target_morning_soc: 30          # Unload to 30% in the morning
  soc_floor: 10              # Never go below 10%
  cheap_soc_target: 100      # Fill to 100% during cheap hours

  # Pricing (Dutch defaults)
  surcharge: 0.11
  price_discharge: 0.45      # Discharge when raw > €0.45
  price_charge: -0.15        # Charge when raw < -€0.15
  min_arbitrage_margin: 0.07 # Need 7c spread for the evening hold-vs-sell (P4)
  afternoon_margin: 0.05     # Evening peak import must beat now by 5c (P3)

  # Adaptive spread window
  min_window_h: 1.5
  rerun_debounce_s: 3.0

  # Time windows
  afternoon_start: 15
  afternoon_end: 18
  afternoon_window_h: 3.0
  evening_peak_start: 19
  evening_peak_end: 23

  # Entity IDs
  strategy_select: select.sessy_battery_alt9_power_strategy
  grid_target: number.sessy_pwkn_grid_target
  battery_setpoint: number.sessy_battery_alt9_power_setpoint
  soc_sensor: sensor.sessy_battery_alt9_state_of_charge
  price_sensor: sensor.sessy_dnhh_energy_price
  status_sensor: sensor.sessy_strategy_status

  # Operating mode
  mode_select: select.home_battery_mode
  setpoint_entity: number.home_battery_setpoint
  sessy_dynamic_option: roi
  eco_option: eco
  idle_option: idle

  # Live tuning helpers
  target_afternoon_charging_entity: number.home_battery_target_afternoon_charging
  target_peak_discharge_entity: number.home_battery_target_peak_discharge
  target_morning_soc_entity: number.home_battery_target_morning_soc
  soc_floor_entity: number.home_battery_soc_floor
  cheap_soc_target_entity: number.home_battery_soc_ceiling
  price_discharge_entity: number.home_battery_price_discharge
  price_charge_entity: number.home_battery_price_charge
  min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
  afternoon_margin_entity: number.home_battery_afternoon_margin
```

---

## Price Basis: Raw vs Import

**Critical concept**: The Sessy integration provides **raw export prices** (what the grid pays you for exported energy). Your **import price** (what you pay to import) is the raw price plus the surcharge:

```
import_price = raw_price + surcharge
```

All strategy thresholds (`price_discharge`, `price_charge`) are specified in **raw prices**.

| Threshold | Raw Price | Import Equivalent (with 0.11 surcharge) |
|-----------|-----------|--------------------------------------|
| `price_discharge` | > €0.39 | > €0.50 |
| `price_charge` | < -€0.10 | < €0.01 |

**Example**: If `price_discharge = 0.39` and `surcharge = 0.11`:
- When raw price = €0.45 → import price = €0.56 → **Discharge triggers**
- When raw price = €0.35 → import price = €0.46 → No discharge

This means you're effectively avoiding import at €0.50+ and capturing export at €0.39+.

---

## Validation Rules

1. **Required entities**: `strategy_select`, `grid_target`, `battery_setpoint`, `soc_sensor`, `price_sensor`, `status_sensor` must be valid entity IDs in your Home Assistant.

2. **Positive values**: `capacity_wh`, `max_power_w`, `min_window_h`, `rerun_debounce_s` must be > 0.

3. **Percentage ranges**: SOC values (`target_afternoon_charging`, `target_peak_discharge`, `target_morning_soc`, `soc_floor`, `cheap_soc_target`) must be 0-100.

4. **Time windows**: `afternoon_start` < `afternoon_end`, `evening_peak_start` < `evening_peak_end`.

---

## Tips

1. **Start with defaults**: The default values work well for most Dutch installations. Only adjust after observing behavior for a few days.

2. **Adjust `soc_floor` first**: If you frequently run out of battery in the morning, increase `soc_floor`.

3. **Tune price thresholds**: If the strategy discharges/charges too aggressively, adjust `price_discharge` and `price_charge`. Remember these are raw prices.

4. **Extend afternoon window for large batteries**: If you have a >5 kWh battery and start the afternoon window below 50% SOC, consider increasing `afternoon_window_h` or starting earlier with `afternoon_start`.

5. **Verify entity IDs**: Use Home Assistant's **Developer Tools → States** to confirm your Sessy entity IDs before configuring.

---

## See Also

- [Entity Reference](../entity-reference.md) — All entities used and created by the app
- [Live Tuning Entities](../live-tuning-entities.md) — Runtime-adjustable helpers
- [Strategy Priority Chain](../../explanation/strategy-priority-chain.md) — How the strategy makes decisions
- [Setpoint Types Explained](../../explanation/setpoint-types-explained.md) — Understanding api vs nom modes
