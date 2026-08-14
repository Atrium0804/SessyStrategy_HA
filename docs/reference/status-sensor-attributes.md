# Status Sensor Attributes

*Last updated: 2026-08-01 | Part of [Reference Documentation](../index.md)*

---

## Overview

The `sensor.sessy_strategy_status` entity is created and maintained by the SessyStrategy app. It serves as the primary monitoring and debugging interface, providing complete visibility into the strategy's current state and decision context.

**Entity type:** Sensor
**Default ID:** `sensor.sessy_strategy_status` (configurable via `status_sensor` in apps.yaml)
**State:** Current active season (`summer` or `winter`)
**Attributes:** Comprehensive decision context (see tables below)

---

## Complete Attribute List

### Always Present Attributes

These attributes are updated on every strategy cycle, regardless of the active branch.

| Attribute | Type | Description | Example | When Updated |
|---|---|---|---|---|
| `active_branch` | str | The currently active priority branch | `discharge`, `prepeak_charge`, `default` | Every cycle |
| `season_mode_source` | str | Source of season mode (apps.yaml or entity) | `auto`, `summer`, `winter` | Every cycle |
| `daily_min_price_hour` | int \| None | Hour of today's minimum raw price | `3` (03:00) | Every cycle |
| `daily_min_price` | float \| None | Value of today's minimum raw price | `0.08500` | Every cycle |
| `soc` | float | Current State of Charge | `65.5` | Every cycle |
| `raw_price` | float | Current raw export price | `0.25450` | Every cycle |
| `import_price` | float | Current import price (raw + surcharge) | `0.36450` | Every cycle |
| `soc_target` | float | Active SOC target | `70.0` | Every cycle |
| `soc_floor` | float | Active SOC floor | `20.0` | Every cycle |
| `cheap_soc_target` | float | Active cheap SOC target | `100.0` | Every cycle |
| `price_discharge` | float | Active discharge price threshold | `0.39` | Every cycle |
| `price_charge` | float | Active charge price threshold | `-0.10` | Every cycle |
| `min_arbitrage_margin` | float | Active minimum arbitrage margin | `0.05` | Every cycle |
| `prepeak_start` | int | Active pre-peak start hour | `16` | Every cycle |
| `prepeak_end` | int | Active pre-peak end hour | `18` | Every cycle |
| `prepeak_window_h` | float | Active pre-peak spread window | `2.0` | Every cycle |

### Season-Specific Attributes

These attributes provide configuration visibility for seasonal overrides.

| Attribute | Type | Description | Example | When Updated |
|---|---|---|---|---|
| `season_day_start` | int | Daytime start hour for season inference | `8` | Every cycle |
| `season_day_end` | int | Daytime end hour for season inference | `18` | Every cycle |
| `season_auto_fallback` | str | Fallback season when auto-inference fails | `winter` | Every cycle |

---

## Attribute Details by Branch

The `active_branch` attribute indicates which priority rule matched. Each branch may include additional context-specific information.

### Priority 1: Discharge (`active_branch: "discharge"`)

**Trigger:** `price > price_discharge`

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `discharge` |
| All common attributes | | See above | |

**What it means:** The battery is discharging because the raw price is above the discharge threshold. Power is being spread over the adaptive window to avoid high inverter losses.

### Priority 2: Cheap Charge (`active_branch: "cheap_charge"` or `"cheap_charge_full"`)

**Trigger:** `price < price_charge`

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `cheap_charge` or `cheap_charge_full` |
| All common attributes | | See above | |

**`cheap_charge_full`:** SOC is already at or above `cheap_soc_target`, so the strategy holds at grid setpoint 0W.

### Priority 3: Pre-Peak Charge (`active_branch: "prepeak_charge"`, `"prepeak_full"`, or `"prepeak_skip"`)

**Trigger:** Inside pre-peak window, SOC < target, and arbitrage margin is sufficient

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `prepeak_charge`, `prepeak_full`, `prepeak_skip` |
| All common attributes | | See above | |

**Variants:**
- `prepeak_charge`: Actively charging toward `soc_target`
- `prepeak_full`: SOC already at target, holding at grid 0W
- `prepeak_skip`: Price spread too small, not worth charging

### Priority 4: Evening Peak Excess Discharge (`active_branch: "evening_peak_excess"`)

**Trigger:** Inside evening peak window, SOC > target, no remaining spike

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `evening_peak_excess` |
| All common attributes | | See above | |

**What it means:** The battery has excess SOC above target with no further price spikes expected, so it's discharging the surplus.

### Priority 5: Default (`active_branch: "default"`)

**Trigger:** None of the above

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `default` |
| All common attributes | | See above | |

**What it means:** Grid setpoint is 0W — absorbing solar, blocking export.

---

## Manual Mode Attributes

When the strategy is in a manual or standby mode, the status sensor uses a simplified publish method with different attributes.

### Manual Grid Setpoint (`active_branch: "manual_grid"`)

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `manual_grid` |
| `setpoint` | float | The manual grid setpoint value | `500.0` |
| `sessy_strategy` | str | The Sessy strategy option | `nom` |

### Manual Battery Setpoint (`active_branch: "manual_battery"`)

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `manual_battery` |
| `setpoint` | float | The manual battery setpoint value | `-1000.0` |
| `sessy_strategy` | str | The Sessy strategy option | `api` |

### Standby Modes

| Active Branch | Sessy Strategy | Description |
|---|---|---|
| `idle` | `idle` | Battery parked, no action |
| `sessy_dynamic` | `roi` (or configured value) | Handed control back to Sessy's dynamic schedule |
| `eco` | `eco` | Handed control to Sessy's eco mode |

---

## Type Information

| Attribute | Data Type | Format | Notes |
|---|---|---|---|
| `active_branch` | string | lowercase_with_underscores | Always present |
| `season_mode_source` | string | lowercase | auto, summer, or winter |
| `daily_min_price_hour` | integer \| None | 0-23 | Null if price data unavailable |
| `daily_min_price` | float \| None | any | Null if price data unavailable |
| `soc` | float | 0-100 | Rounded to 2 decimal places |
| `raw_price` | float | any | Rounded to 5 decimal places |
| `import_price` | float | any | Rounded to 5 decimal places |
| `soc_target` | float | 0-100 | From live entity or apps.yaml |
| `soc_floor` | float | 0-100 | From live entity or apps.yaml |
| `cheap_soc_target` | float | 0-100 | From live entity or apps.yaml |
| `price_discharge` | float | any | From live entity or apps.yaml |
| `price_charge` | float | any | From live entity or apps.yaml |
| `min_arbitrage_margin` | float | ≥ 0 | From live entity or apps.yaml |
| `prepeak_start` | integer | 0-23 | From seasonal config |
| `prepeak_end` | integer | 0-23 | From seasonal config |
| `prepeak_window_h` | float | > 0 | From seasonal config |
| `season_day_start` | integer | 0-23 | From apps.yaml |
| `season_day_end` | integer | 0-23 | From apps.yaml |
| `season_auto_fallback` | string | lowercase | From apps.yaml |

---

## Examples

### Full Status Sensor Output (Priority 1 Active)

```yaml
entity_id: sensor.sessy_strategy_status
state: summer
attributes:
  active_branch: discharge
  season_mode_source: auto
  daily_min_price_hour: 3
  daily_min_price: -0.085
  soc: 72.5
  raw_price: 0.45200
  import_price: 0.56200
  soc_target: 70.0
  soc_floor: 20.0
  cheap_soc_target: 100.0
  price_discharge: 0.39
  price_charge: -0.10
  min_arbitrage_margin: 0.05
  prepeak_start: 16
  prepeak_end: 18
  prepeak_window_h: 2.0
  season_day_start: 8
  season_day_end: 18
  season_auto_fallback: winter
```

### Manual Mode Status

```yaml
entity_id: sensor.sessy_strategy_status
state: manual_grid
attributes:
  active_branch: manual_grid
  setpoint: 500.0
  sessy_strategy: nom
```

---

## When Attributes Update

- **Every 5 minutes**: Regular strategy cycle updates all attributes
- **Immediately**: When any live-tuning entity changes (after debounce delay)
- **On season change**: When the inferred or set season changes
- **On startup**: Initial publish with all current values

---

## Usage Patterns

### Debugging Strategy Decisions

The status sensor is the first place to look when debugging unexpected behavior:

1. **Check `active_branch`**: Which priority matched?
2. **Check price values**: Is `raw_price` above/below expected thresholds?
3. **Check SOC**: Is the battery at expected levels?
4. **Check season**: Is the correct season active?

**Example diagnostic questions:**

- "Why didn't it discharge at €0.45?" → Check if `price_discharge` was higher than 0.45
- "Why didn't it charge during cheap hours?" → Check if `price_charge` was lower than the actual price, or if SOC was already at `cheap_soc_target`
- "Why is it in summer mode in December?" → Check `season_mode_source` and `daily_min_price_hour`

### Monitoring in Dashboards

The status sensor attributes can be displayed in dashboards:

```yaml
# Entity card showing key attributes
type: entity
entity: sensor.sessy_strategy_status
secondary_info: "Branch: [[ active_branch ]] | SOC: [[ soc ]]% | Price: [[ raw_price ]]"

# Attributes card
type: attributes
entity: sensor.sessy_strategy_status
state_color: true
```

### Automations Based on Strategy State

Trigger automations based on strategy decisions:

```yaml
automation:
  - alias: "Notify on price spike discharge"
    trigger:
      - platform: state
        entity_id: sensor.sessy_strategy_status
        attribute: active_branch
        to: discharge
    action:
      - service: notify.mobile_app
        data:
          message: "SessyStrategy: Price spike discharge active!"
          data:
            price: "{{ state_attr('sensor.sessy_strategy_status', 'raw_price') }}"
            soc: "{{ state_attr('sensor.sessy_strategy_status', 'soc') }}%"
```

### History and Trend Analysis

The numeric attributes (SOC, prices, thresholds) can be graphed in history:

```yaml
type: custom:apexcharts-card
series:
  - entity: sensor.sessy_strategy_status
    attribute: soc
    name: SOC
    type: line
  - entity: sensor.sessy_strategy_status
    attribute: raw_price
    name: Raw Price
    type: line
    yaxis_id: price
```

---

## Data Flow

```
Home Assistant State
    ↓
_price_sensor (energy_prices attribute) → daily_min_price_hour, daily_min_price
    ↓
_soc_sensor → soc
    ↓
Strategy Decision Engine
    ↓
Publish to status_sensor:
    - state = active_season
    - attributes = all context + active_branch
    ↓
Home Assistant Updates Entity
```

---

## See Also

- [Entity Reference](entity-reference.md) — All entities used by the app
- [Configuration Reference](configuration/apps-yaml.md) — apps.yaml parameters that map to these attributes
- [Live Tuning Entities](live-tuning-entities.md) — How to make these values adjustable at runtime
- [Debug Strategy Decisions](../how-to/debug-strategy-decisions.md) — Practical guide using these attributes
- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — Understanding what each branch does
