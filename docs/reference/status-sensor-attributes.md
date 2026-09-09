# Status Sensor Attributes

*Last updated: 2026-08-01 | Part of [Reference Documentation](../index.md)*

---

## Overview

The `sensor.sessy_strategy_status` entity is created and maintained by the SessyStrategy app. It serves as the primary monitoring and debugging interface, providing complete visibility into the strategy's current state and decision context.

**Entity type:** Sensor
**Default ID:** `sensor.sessy_strategy_status` (configurable via `status_sensor` in apps.yaml)
**State:** Name of the currently active branch (e.g. `default`, `discharge`, `cheap_charge`, `afternoon_charge`, `evening_peak_selloff`, `morning_selloff`, plus manual/standby branches)
**Attributes:** Comprehensive decision context (see tables below)

---

## Complete Attribute List

### Always Present Attributes

These attributes are updated on every strategy cycle, regardless of the active branch.

| Attribute | Type | Description | Example | When Updated |
|---|---|---|---|---|
| `active_branch` | str | The currently active priority branch | `discharge`, `afternoon_charge`, `default` | Every cycle |
| `soc` | float | Current State of Charge | `65.5` | Every cycle |
| `price` | float | Current market price | `0.25450` | Every cycle |
| `target_afternoon_charging` | float | Active afternoon charge target (P3) | `70.0` | Every cycle |
| `target_peak_discharge` | float | Active evening peak sell-off target (P4) | `70.0` | Every cycle |
| `target_morning_soc` | float | Active morning sell-off target (P5) | `30.0` | Every cycle |
| `soc_floor` | float | Active SOC floor | `20.0` | Every cycle |
| `cheap_soc_target` | float | Active cheap SOC target | `100.0` | Every cycle |
| `price_discharge` | float | Active discharge price threshold | `0.39` | Every cycle |
| `price_charge` | float | Active charge price threshold | `-0.10` | Every cycle |
| `min_arbitrage_margin` | float | Active minimum arbitrage margin (P4) | `0.05` | Every cycle |
| `afternoon_margin` | float | Active afternoon charge margin (P3) | `0.05` | Every cycle |
| `afternoon_start` | int | Active afternoon start hour | `16` | Every cycle |
| `afternoon_end` | int | Active afternoon end hour | `18` | Every cycle |
| `afternoon_window_h` | float | Active afternoon spread window | `2.0` | Every cycle |

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

### Priority 3: Afternoon Charge (`active_branch: "afternoon_charge"`, `"afternoon_full"`, or `"afternoon_skip"`)

**Trigger:** Inside afternoon window, SOC < target, and the evening peak import price beats the current import price by at least `afternoon_margin`

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `afternoon_charge`, `afternoon_full`, `afternoon_skip` |
| All common attributes | | See above | |

**Variants:**
- `afternoon_charge`: Actively charging toward `target_afternoon_charging` to avoid net import at the evening peak
- `afternoon_full`: SOC already at target, holding at grid 0W
- `afternoon_skip`: Evening peak import barely above current import, not worth topping up

### Priority 4: Evening Peak Sell-off Discharge (`active_branch: "evening_peak_selloff"`)

**Trigger:** Inside evening peak window, SOC > target, no remaining spike

| Attribute | Type | Description | Example |
|---|---|---|---|
| `active_branch` | str | Branch identifier | `evening_peak_selloff` |
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
| `soc` | float | 0-100 | Rounded to 2 decimal places |
| `price` | float | any | Rounded to 5 decimal places |
| `target_afternoon_charging` | float | 0-100 | From live entity or apps.yaml |
| `target_peak_discharge` | float | 0-100 | From live entity or apps.yaml |
| `target_morning_soc` | float | 0-100 | From live entity or apps.yaml |
| `soc_floor` | float | 0-100 | From live entity or apps.yaml |
| `cheap_soc_target` | float | 0-100 | From live entity or apps.yaml |
| `price_discharge` | float | any | From live entity or apps.yaml |
| `price_charge` | float | any | From live entity or apps.yaml |
| `min_arbitrage_margin` | float | ≥ 0 | From live entity or apps.yaml |
| `afternoon_margin` | float | 0-0.5 | From live entity or apps.yaml |
| `afternoon_start` | integer | 0-23 | From apps.yaml |
| `afternoon_end` | integer | 0-23 | From apps.yaml |
| `afternoon_window_h` | float | > 0 | Derived spread window |

---

## Examples

### Full Status Sensor Output (Priority 1 Active)

```yaml
entity_id: sensor.sessy_strategy_status
state: discharge
attributes:
  active_branch: discharge
  soc: 72.5
  price: 0.45200
  target_afternoon_charging: 70.0
  target_peak_discharge: 70.0
  target_morning_soc: 30.0
  soc_floor: 20.0
  cheap_soc_target: 100.0
  price_discharge: 0.39
  price_charge: -0.10
  min_arbitrage_margin: 0.05
  afternoon_margin: 0.05
  afternoon_start: 16
  afternoon_end: 18
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
- **On startup**: Initial publish with all current values

---

## Usage Patterns

### Debugging Strategy Decisions

The status sensor is the first place to look when debugging unexpected behavior:

1. **Check `active_branch`**: Which priority matched?
2. **Check price values**: Is `price` above/below expected thresholds?
3. **Check SOC**: Is the battery at expected levels?

**Example diagnostic questions:**

- "Why didn't it discharge at €0.45?" → Check if `price_discharge` was higher than 0.45
- "Why didn't it charge during cheap hours?" → Check if `price_charge` was lower than the actual price, or if SOC was already at `cheap_soc_target`

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
price_sensor (energy_prices attribute) → price
    ↓
soc_sensor → soc
    ↓
Strategy Decision Engine
    ↓
Publish to status_sensor:
    - state = active_branch
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
