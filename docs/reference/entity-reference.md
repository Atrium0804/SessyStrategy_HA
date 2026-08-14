# Entity Reference

*Last updated: 2026-08-01 | Part of [Reference Documentation](../index.md)*

---

## Overview

The SessyStrategy app interacts with Home Assistant through various entities. These are categorized as:

- **Required Entities**: Must exist and be configured in `apps.yaml`
- **Optional Entities**: Provide enhanced functionality when available
- **Created Entities**: Created and maintained by the app itself

All entity IDs are configurable via `apps.yaml`. The defaults shown below are from the author's installation and **will not match your setup** — you must map them to your own Sessy entities.

---

## Required Entities

These entities **must** be configured in `apps.yaml` and must exist in your Home Assistant. The app will log warnings and skip cycles if these are unavailable.

### Sensors (Read-only)

| Entity ID (default) | Type | Purpose | Example Value | Used In |
|---|---|---|---|---|
| `sensor.sessy_battery_alt9_state_of_charge` | sensor | Current battery State of Charge | `65.5` (percent) | Setpoint calculations, all priority branches |
| `sensor.sessy_dnhh_energy_price` | sensor | Current raw export energy price | `0.25450` (€/kWh) | Price threshold decisions |

### Controls (Read/Write)

| Entity ID (default) | Type | Purpose | Values | Used In |
|---|---|---|---|---|
| `select.sessy_battery_alt9_power_strategy` | select | Sessy power strategy selector | `nom`, `api`, `roi`, `eco`, `idle` | Strategy mode switching |
| `number.sessy_pwkn_grid_target` | number | Grid power target | -2200 to +2200 W | Grid setpoint mode (Priority 4, 5) |
| `number.sessy_battery_alt9_power_setpoint` | number | Battery power setpoint | -2200 to +2200 W | Battery setpoint mode (Priority 1-3) |
| `sensor.sessy_strategy_status` | sensor | App status sensor (created by app) | `summer` or `winter` (state), multiple attributes | Status monitoring |

### Configuration in apps.yaml

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  # REQUIRED: Map these to your entities
  strategy_select: select.sessy_battery_alt9_power_strategy
  grid_target: number.sessy_pwkn_grid_target
  battery_setpoint: number.sessy_battery_alt9_power_setpoint
  soc_sensor: sensor.sessy_battery_alt9_state_of_charge
  price_sensor: sensor.sessy_dnhh_energy_price
  status_sensor: sensor.sessy_strategy_status
```

**How to find your entity IDs:**
1. Go to **Developer Tools → States** in Home Assistant
2. Filter for `sessy` entities
3. Note the exact entity IDs for your battery, price sensor, and strategy select

---

## Optional Entities

These entities are optional but enable additional functionality when configured.

### Mode and Control

| Entity ID | apps.yaml Key | Type | Purpose | Values | Default Behavior if Unset |
|---|---|---|---|---|---|
| `select.home_battery_mode` | `mode_select` | select | Master mode selector | `Optimized`, `Grid setpoint`, `Battery setpoint`, `Sessy dynamic`, `Eco`, `Idle` | Uses `optimized` mode only |
| `number.home_battery_setpoint` | `setpoint_entity` | number | Manual setpoint for grid/battery modes | W | Manual modes unavailable |
| `input_boolean.sessy_strategy_enabled` | `enable_switch` | input_boolean | Legacy master enable switch | `on`/`off` | Always enabled (if `mode_select` is set) |

### Live Tuning Helpers

These allow runtime adjustment without restarting AppDaemon. The app reads these each cycle and falls back to static `apps.yaml` values if the entity is unavailable.

| Entity ID | apps.yaml Key | Type | Purpose | Range | Example |
|---|---|---|---|---|---|
| `number.home_battery_soc_target` | `soc_target_entity` | number | Live SOC target override | 0-100 % | Overrides `soc_target` |
| `number.home_battery_soc_floor` | `soc_floor_entity` | number | Live SOC floor override | 0-100 % | Overrides `soc_floor` |
| `number.home_battery_soc_ceiling` | `cheap_soc_target_entity` | number | Live cheap SOC target override | 0-100 % | Overrides `cheap_soc_target` |
| `number.home_battery_price_discharge` | `price_discharge_entity` | number | Live discharge threshold | any €/kWh | Overrides `price_discharge` |
| `number.home_battery_price_charge` | `price_charge_entity` | number | Live charge threshold | any €/kWh | Overrides `price_charge` |
| `number.home_battery_min_arbitrage_margin` | `min_arbitrage_margin_entity` | number | Live arbitrage margin | ≥ 0 €/kWh | Overrides `min_arbitrage_margin` |
| `input_select.sessy_season_mode` | `season_mode_entity` | input_select | Live season mode | `auto`, `summer`, `winter` | Overrides `season_mode` |

**Configuration example:**

```yaml
sessy_strategy:
  # ... other config ...

  # Live tuning entities
  mode_select: select.home_battery_mode
  setpoint_entity: number.home_battery_setpoint
  soc_target_entity: number.home_battery_soc_target
  soc_floor_entity: number.home_battery_soc_floor
  cheap_soc_target_entity: number.home_battery_soc_ceiling
  price_discharge_entity: number.home_battery_price_discharge
  price_charge_entity: number.home_battery_price_charge
  min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
  season_mode_entity: input_select.sessy_season_mode

  # Sessy strategy option strings (for standby modes)
  sessy_dynamic_option: roi
  eco_option: eco
  idle_option: idle
```

### Sessy Integration Entities (for reference)

These entities from the Sessy integration are useful for monitoring and dashboarding:

| Entity | Description | Attribute | Purpose |
|---|---|---|---|
| `sensor.sessy_dnhh_energy_price` | Energy price | `energy_prices` | Full day's price schedule |
| `sensor.sessy_dnhh_power_schedule` | Sessy's schedule | `dynamic_schedule` | Sessy's planned power schedule |
| `sensor.sessy_pwkn_p1_power` | Grid power | state | Actual grid power (negative = export) |
| `sensor.sessy_battery_alt9_power` | Battery power | state | Actual battery power (positive = discharge) |
| `sensor.sessy_battery_alt9_pv_power` | PV power | state | Current PV production |
| `sensor.sessy_battery_alt9_load_power` | Load power | state | Household load |
| `sensor.sessy_battery_alt9_system_state` | System state | state | `running`, `full`, `empty`, etc. |

---

## Entities Created by the App

The app creates and maintains these entities:

### Status Sensor

| Entity ID | Type | State | Attributes | Purpose |
|---|---|---|---|---|
| `sensor.sessy_strategy_status` | sensor | `summer` or `winter` (active season) | See [Status Sensor Attributes](status-sensor-attributes.md) | Strategy state and decision context |

This is the primary entity for monitoring the strategy's decisions and current state. The state shows the active season, and the attributes contain all the context used in the latest decision.

**Note**: You can customize the entity ID by setting `status_sensor` in `apps.yaml`.

---

## Entity Types Summary

### Input Entities (App Reads)

1. **Sensors**: SOC, price data
2. **Selects**: Mode selection, season mode
3. **Numbers**: Manual setpoint, live tuning values
4. **Input Boolean**: Legacy enable switch

### Output Entities (App Writes)

1. **Selects**: `strategy_select` (switches between `nom` and `api`)
2. **Numbers**: `grid_target`, `battery_setpoint`
3. **Sensors**: `status_sensor` (created and updated by app)

---

## Home Battery Integration Entities

The optional Home Battery custom integration (`custom_components/home_battery`) creates a unified interface and provides these entities:

### Controls

| Entity | apps.yaml Key | Description |
|---|---|---|
| `select.home_battery_mode` | `mode_select` | Master mode: Optimized, Grid setpoint, Battery setpoint, Sessy dynamic, Eco, Idle |
| `number.home_battery_setpoint` | `setpoint_entity` | Manual setpoint (interpretation depends on mode) |
| `number.home_battery_soc_target` | `soc_target_entity` | Live SOC target |
| `number.home_battery_soc_floor` | `soc_floor_entity` | Live SOC floor |
| `number.home_battery_soc_ceiling` | `cheap_soc_target_entity` | Live cheap SOC ceiling |
| `number.home_battery_price_discharge` | `price_discharge_entity` | Live discharge threshold |
| `number.home_battery_price_charge` | `price_charge_entity` | Live charge threshold |
| `number.home_battery_min_arbitrage_margin` | `min_arbitrage_margin_entity` | Live arbitrage margin |
| `input_select.sessy_season_mode` | `season_mode_entity` | Live season mode |

### Sensors

| Entity | Description |
|---|---|
| `sensor.home_battery_soc` | Current SOC % |
| `sensor.home_battery_battery_power` | Battery net power (positive = discharge) |
| `sensor.home_battery_grid_power` | Grid net power (negative = export) |
| `sensor.home_battery_system_state` | System state |
| `sensor.home_battery_active_strategy` | Active power strategy |
| `sensor.home_battery_sessy_strategy` | Underlying Sessy strategy |
| `sensor.home_battery_active_substrategy` | Active rule with friendly name |
| `sensor.home_battery_actual_setpoint` | Actual setpoint being targeted |

---

## Entity Mapping Guide

When setting up SessyStrategy, you need to map the default entity IDs to your own Sessy entities. Here's how:

1. **Identify your Sessy battery ID**: Check your Sessy integration entities. They typically follow patterns like:
   - `sensor.sessy_battery_<ID>_state_of_charge`
   - `number.sessy_<ID>_grid_target`
   - `number.sessy_battery_<ID>_power_setpoint`
   - `select.sessy_battery_<ID>_power_strategy`

2. **Find your price sensor**: This is usually from your energy provider integration:
   - DSMR: `sensor.dsmr_energy_price` or similar
   - Nordic Energy: `sensor.nordic_energy_price`
   - Sessy's own: `sensor.sessy_<provider>_energy_price`

3. **Update apps.yaml**: Replace the default entity IDs with your own:

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  # Replace these with your entities
  strategy_select: select.sessy_battery_my_battery_id_power_strategy
  grid_target: number.sessy_my_id_grid_target
  battery_setpoint: number.sessy_battery_my_battery_id_power_setpoint
  soc_sensor: sensor.sessy_battery_my_battery_id_state_of_charge
  price_sensor: sensor.my_energy_price
  status_sensor: sensor.sessy_strategy_status
```

---

## Verification Checklist

After configuration, verify entities are working:

- [ ] `soc_sensor` shows a numeric percentage value
- [ ] `price_sensor` shows a numeric price and has `energy_prices` attribute
- [ ] `strategy_select` can be manually set to `nom` and `api`
- [ ] `grid_target` accepts numeric values
- [ ] `battery_setpoint` accepts numeric values
- [ ] `status_sensor` is created and shows season state after app startup

---

## See Also

- [Configuration Reference](configuration/apps-yaml.md) — All apps.yaml parameters
- [Live Tuning Entities](live-tuning-entities.md) — Runtime-adjustable helpers
- [Status Sensor Attributes](status-sensor-attributes.md) — Complete attribute list
- [Service Calls](service-calls.md) — Services used by the app
- [Setpoint Types Explained](../explanation/setpoint-types-explained.md) — Understanding control modes
