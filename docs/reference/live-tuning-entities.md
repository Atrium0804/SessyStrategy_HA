# Live Tuning Entities

*Last updated: 2026-08-01 | Part of [Reference Documentation](../index.md)*

---

## Overview

Live tuning entities allow you to adjust SessyStrategy behavior **without restarting AppDaemon**. These are optional Home Assistant helper entities (typically `input_number` for numeric values, `input_select` for modes) that the app reads each cycle. When a live entity is configured and available, its value overrides the corresponding static `apps.yaml` value.

**Key benefits:**
- Change thresholds from a dashboard or your phone
- Tune behavior in real-time based on observations
- Create automations that adjust values based on conditions
- Graph tuning values in history for analysis

---

## Purpose

The app runs every 5 minutes, and **immediately whenever a live input changes** (with a debounce delay). This means:

1. You can create input helpers in Home Assistant (via **Settings → Devices & Services → Helpers**)
2. Link them to the app via `apps.yaml` configuration
3. Adjust values through the HA UI
4. Changes take effect within seconds (after the debounce period)

---

## Entity Table

### Numeric Helpers (input_number)

| Entity ID | apps.yaml Key | Description | Range | Default Fallback | Unit |
|---|---|---|---|---|---|
| `number.home_battery_soc_target` | `soc_target_entity` | Target SOC for pre-peak charge | 0-100 | `soc_target` from apps.yaml | % |
| `number.home_battery_soc_floor` | `soc_floor_entity` | Minimum SOC floor | 0-100 | `soc_floor` from apps.yaml | % |
| `number.home_battery_soc_ceiling` | `cheap_soc_target_entity` | Target SOC for cheap-price charging | 0-100 | `cheap_soc_target` from apps.yaml | % |
| `number.home_battery_price_discharge` | `price_discharge_entity` | Price threshold for discharge | any | `price_discharge` from apps.yaml | €/kWh |
| `number.home_battery_price_charge` | `price_charge_entity` | Price threshold for charging | any | `price_charge` from apps.yaml | €/kWh |
| `number.home_battery_min_arbitrage_margin` | `min_arbitrage_margin_entity` | Minimum spread for pre-peak charge | ≥ 0 | `min_arbitrage_margin` from apps.yaml | €/kWh |

### Mode Selector (input_select)

| Entity ID | apps.yaml Key | Description | Options | Default Fallback |
|---|---|---|---|---|
| `input_select.sessy_season_mode` | `season_mode_entity` | Live season mode override | `auto`, `summer`, `winter` | `season_mode` from apps.yaml |

---

## Setup Instructions

### Step 1: Create Helper Entities

Use Home Assistant's UI to create the helpers:

1. Go to **Settings → Devices & Services → Helpers**
2. Click **Add Helper** → **Number** (for numeric values) or **Select** (for season mode)
3. Configure each helper:

**Numeric Helpers (input_number):**

| Name | Entity ID | Min | Max | Step | Unit | Icon |
|------|-----------|-----|-----|------|------|------|
| SOC Target | `number.home_battery_soc_target` | 0 | 100 | 1 | % | mdi:battery-60 |
| SOC Floor | `number.home_battery_soc_floor` | 0 | 100 | 1 | % | mdi:battery-outline |
| SOC Ceiling | `number.home_battery_soc_ceiling` | 0 | 100 | 1 | % | mdi:battery |
| Price Discharge | `number.home_battery_price_discharge` | -1 | 1 | 0.01 | €/kWh | mdi:lightning-bolt |
| Price Charge | `number.home_battery_price_charge` | -1 | 1 | 0.01 | €/kWh | mdi:lightning-bolt |
| Min Arbitrage Margin | `number.home_battery_min_arbitrage_margin` | 0 | 0.5 | 0.01 | €/kWh | mdi:swap-horizontal |

**Mode Selector (input_select):**

| Name | Entity ID | Options | Icon |
|------|-----------|---------|------|
| Season Mode | `input_select.sessy_season_mode` | auto, summer, winter | mdi:weather-sunny |

### Step 2: Link to apps.yaml

Add the entity references to your `apps.yaml`:

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  
  # Static defaults (used when live entities are unavailable)
  soc_target: 70
  soc_floor: 20
  cheap_soc_target: 100
  price_discharge: 0.39
  price_charge: -0.10
  min_arbitrage_margin: 0.05
  season_mode: auto
  
  # Live tuning entity links
  soc_target_entity: number.home_battery_soc_target
  soc_floor_entity: number.home_battery_soc_floor
  cheap_soc_target_entity: number.home_battery_soc_ceiling
  price_discharge_entity: number.home_battery_price_discharge
  price_charge_entity: number.home_battery_price_charge
  min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
  season_mode_entity: input_select.sessy_season_mode
```

### Step 3: Create a Dashboard

Add the helpers to a dashboard for easy access:

```yaml
# Example Lovelace card
card:
  type: entities
  title: SessyStrategy Live Tuning
  show_header_toggle: false
  entities:
    - entity: input_select.sessy_season_mode
      name: Season Mode
    - entity: number.home_battery_soc_target
      name: SOC Target
    - entity: number.home_battery_soc_floor
      name: SOC Floor
    - entity: number.home_battery_soc_ceiling
      name: SOC Ceiling
    - entity: number.home_battery_price_discharge
      name: Discharge Price
    - entity: number.home_battery_price_charge
      name: Charge Price
    - entity: number.home_battery_min_arbitrage_margin
      name: Arbitrage Margin
```

---

## Usage Example

With live entities configured:

1. **Morning observation**: You notice the battery is running low too early
2. **Dashboard action**: Increase `soc_floor` from 20% to 25%
3. **Immediate effect**: The next strategy cycle (within seconds) uses the new 25% floor
4. **No restart needed**: AppDaemon doesn't need to be restarted

The app logs the change:

```
INFO sessy_strategy: Input number.home_battery_soc_floor changed 20 → 25 — re-running in 2s
```

---

## Fallback Behavior

The app always falls back to the static `apps.yaml` value if:

- The live entity is not configured (null in apps.yaml)
- The entity doesn't exist in Home Assistant
- The entity exists but has no valid state (None, unavailable, etc.)
- The entity state cannot be parsed as a float (for numeric helpers)

This ensures the strategy continues to work even if a live entity is temporarily unavailable.

---

## HA UI Example

Here's a complete YAML for creating the helpers via YAML (alternative to UI):

```yaml
# Add to your configuration.yaml or a package file

input_number:
  home_battery_soc_target:
    name: SOC Target
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "%"
    icon: mdi:battery-60
    initial: 70
    
  home_battery_soc_floor:
    name: SOC Floor
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "%"
    icon: mdi:battery-outline
    initial: 20
    
  home_battery_soc_ceiling:
    name: SOC Ceiling
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "%"
    icon: mdi:battery
    initial: 100
    
  home_battery_price_discharge:
    name: Discharge Price
    min: -1
    max: 1
    step: 0.01
    unit_of_measurement: "€/kWh"
    icon: mdi:lightning-bolt
    initial: 0.39
    
  home_battery_price_charge:
    name: Charge Price
    min: -1
    max: 1
    step: 0.01
    unit_of_measurement: "€/kWh"
    icon: mdi:lightning-bolt
    initial: -0.10
    
  home_battery_min_arbitrage_margin:
    name: Min Arbitrage Margin
    min: 0
    max: 0.5
    step: 0.01
    unit_of_measurement: "€/kWh"
    icon: mdi:swap-horizontal
    initial: 0.05

input_select:
  sessy_season_mode:
    name: Season Mode
    options:
      - auto
      - summer
      - winter
    initial: auto
    icon: mdi:weather-sunny
```

---

## Home Battery Integration

The [Home Battery custom integration](https://github.com/PimDoos/ha-sessy/tree/main/custom_components/home_battery) provides these live tuning entities automatically when installed:

- `number.home_battery_soc_target`
- `number.home_battery_soc_floor`
- `number.home_battery_soc_ceiling`
- `number.home_battery_price_discharge`
- `number.home_battery_price_charge`
- `number.home_battery_min_arbitrage_margin`
- `input_select.sessy_season_mode`

These are pre-configured to work with SessyStrategy. Simply reference them in your `apps.yaml` as shown above.

---

## Advanced Usage

### Automation-Based Tuning

You can create automations that adjust live entities based on conditions:

```yaml
automation:
  - alias: "Increase SOC floor on cold days"
    trigger:
      - platform: numeric_state
        entity_id: sensor.outside_temperature
        below: 5
    action:
      - service: number.set_value
        entity_id: number.home_battery_soc_floor
        value: 30
    
  - alias: "Reset SOC floor on warm days"
    trigger:
      - platform: numeric_state
        entity_id: sensor.outside_temperature
        above: 10
    action:
      - service: number.set_value
        entity_id: number.home_battery_soc_floor
        value: 20
```

### Conditional Overrides

Use templates or conditional cards to show/hide helpers based on mode:

```yaml
# Show price helpers only in optimized mode
type: conditional
conditions:
  - entity: select.home_battery_mode
    state: Optimized
card:
  type: entities
  entities:
    - number.home_battery_price_discharge
    - number.home_battery_price_charge
    - number.home_battery_min_arbitrage_margin
```

---

## Debugging

If live entities aren't working:

1. **Check entity exists**: Verify the entity ID in Developer Tools → States
2. **Check app configuration**: Ensure the `*_entity` keys in apps.yaml match your entity IDs
3. **Check app logs**: Look for "Input X changed" messages
4. **Check value type**: Numeric entities must return parseable floats
5. **Check availability**: Entity must have a non-None, non-unavailable state

---

## See Also

- [Configuration Reference](configuration/apps-yaml.md) — Static apps.yaml parameters
- [Entity Reference](entity-reference.md) — All entities used by the app
- [Status Sensor Attributes](status-sensor-attributes.md) — Monitor live values in action
- [Tune Price Thresholds](../how-to/tune-price-thresholds.md) — Practical guide to threshold tuning
- [Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md) — Step-by-step setup guide
