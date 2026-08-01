# Service Calls

*Last updated: 2026-08-01 | Part of [Reference Documentation](../)*

---

## Overview

The SessyStrategy app makes Home Assistant service calls to control the Sessy battery and interact with Home Assistant. All service calls are made through the AppDaemon HASS API (`self.call_service()`).

**Key characteristics:**
- Service calls are wrapped in try-except blocks to handle failures gracefully
- The app logs warnings (not errors) when service calls fail, allowing the strategy to continue
- All service calls are conditional on entity existence checks

---

## Services Used

### 1. `select/select_option`

**Purpose:** Switch the Sessy power strategy between modes.

| Call Location | Parameters | When Called | Purpose |
|---|---|---|---|
| `_set_grid_setpoint()` | `entity_id=strategy_select`, `option="nom"` | Before setting grid target | Switch to grid setpoint mode |
| `_set_battery_setpoint()` | `entity_id=strategy_select`, `option="api"` | Before setting battery setpoint | Switch to battery setpoint mode |
| `_apply_standby()` | `entity_id=strategy_select`, `option=sessy_strategy` | When standing down | Switch to configured Sessy strategy |

**Parameters:**
- `entity_id` (str, required): The strategy select entity
- `option` (str, required): The option to select — `nom`, `api`, or user-configured values

**Example call:**
```python
self.call_service(
    "select/select_option",
    entity_id=self.strategy_select,
    option="nom"
)
```

---

### 2. `number/set_value`

**Purpose:** Set numeric setpoint values for grid or battery power.

| Call Location | Parameters | When Called | Purpose |
|---|---|---|---|
| `_set_grid_setpoint()` | `entity_id=grid_target`, `value=int(round(watts))` | In grid setpoint mode | Set grid power target |
| `_set_battery_setpoint()` | `entity_id=battery_setpoint`, `value=int(round(watts))` | In battery setpoint mode | Set battery power target |

**Parameters:**
- `entity_id` (str, required): The target number entity
- `value` (int, required): The numeric value (rounded to nearest integer)

**Value interpretation:**
- **Grid setpoint (`nom` mode)**: Positive = import from grid, Negative = export to grid
- **Battery setpoint (`api` mode)**: Positive = discharge battery, Negative = charge battery

**Example call:**
```python
self.call_service(
    "number/set_value",
    entity_id=self.grid_target,
    value=int(round(1500))  # 1500W grid import target
)
```

---

### 3. `set_state` (AppDaemon internal)

**Purpose:** Publish the status sensor with current state and attributes.

| Call Location | Parameters | When Called | Purpose |
|---|---|---|---|
| `_publish_status()` | Various | On every strategy decision | Publish full strategy context |
| `_publish_branch()` | Various | On manual/standby modes | Publish lightweight status |

**Parameters:**
- `entity_id` (str, required): The status sensor entity
- `state` (str, required): The active season or branch name
- `attributes` (dict, required): Dictionary of all context attributes

**Example call:**
```python
self.set_state(
    self.status_sensor,
    state=active_season,
    attributes={
        "active_branch": active_branch,
        "soc": round(soc, 2),
        "raw_price": round(raw_price, 5),
        # ... all other attributes
    }
)
```

---

## Call Methods Summary

### Actuator Methods

These methods wrap service calls to set Sessy targets:

| Method | Services Called | Mode | Setpoint Type |
|---|---|---|---|
| `_set_grid_setpoint(watts)` | `select/select_option` (to `nom`), `number/set_value` | Grid setpoint | `grid_target` entity |
| `_set_battery_setpoint(watts)` | `select/select_option` (to `api`), `number/set_value` | Battery setpoint | `battery_setpoint` entity |
| `_apply_standby(option, branch)` | `select/select_option` | Standby | Sessy's own strategy |

### Status Methods

These methods publish the strategy status:

| Method | Service Called | State | Attributes |
|---|---|---|---|
| `_publish_status(branch, **fields)` | `set_state` | active_season | Full context |
| `_publish_branch(branch, **extra)` | `set_state` | branch | Lightweight context |

---

## Service Call Examples by Strategy Branch

### Priority 1: Price-Spike Discharge

```python
# Switch to battery setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="api")
# Set discharge power
self.call_service("number/set_value", entity_id=battery_setpoint, value=1500)
# Publish status
self.set_state(status_sensor, state="summer", attributes={...})
```

### Priority 2: Cheap Charge

```python
# Switch to battery setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="api")
# Set charge power (negative = charge)
self.call_service("number/set_value", entity_id=battery_setpoint, value=-2200)
# Publish status
self.set_state(status_sensor, state="winter", attributes={...})
```

### Priority 3: Pre-Peak Charge

```python
# Switch to battery setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="api")
# Set charge power
self.call_service("number/set_value", entity_id=battery_setpoint, value=-1200)
# Publish status
self.set_state(status_sensor, state="summer", attributes={...})
```

### Priority 4: Evening Peak Excess Discharge

```python
# Switch to grid setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="nom")
# Set grid export target (negative = export)
self.call_service("number/set_value", entity_id=grid_target, value=-500)
# Publish status
self.set_state(status_sensor, state="winter", attributes={...})
```

### Priority 5: Default

```python
# Switch to grid setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="nom")
# Set grid target to 0 (absorb solar, block export)
self.call_service("number/set_value", entity_id=grid_target, value=0)
# Publish status
self.set_state(status_sensor, state="summer", attributes={...})
```

### Manual Grid Setpoint Mode

```python
# Switch to grid setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="nom")
# Set user's manual grid target
self.call_service("number/set_value", entity_id=grid_target, value=1000)
# Publish branch status
self.set_state(status_sensor, state="manual_grid", attributes={"active_branch": "manual_grid", "setpoint": 1000})
```

### Manual Battery Setpoint Mode

```python
# Switch to battery setpoint mode
self.call_service("select/select_option", entity_id=strategy_select, option="api")
# Set user's manual battery target
self.call_service("number/set_value", entity_id=battery_setpoint, value=-800)
# Publish branch status
self.set_state(status_sensor, state="manual_battery", attributes={"active_branch": "manual_battery", "setpoint": -800})
```

### Standby Modes (Idle, Sessy Dynamic, Eco)

```python
# No service calls to setpoints — just switch strategy
self.call_service("select/select_option", entity_id=strategy_select, option="idle")
# Publish branch status
self.set_state(status_sensor, state="idle", attributes={"active_branch": "idle", "sessy_strategy": "idle"})
```

---

## Error Handling

All service calls are wrapped in try-except blocks:

```python
try:
    self.call_service(
        "select/select_option",
        entity_id=self.strategy_select,
        option=strategy_option,
    )
    self.log(f"Strategy → {strategy_option} ({branch})")
except Exception as e:
    self.log(f"Failed to apply standby strategy: {e}", level="WARNING")
```

**Behavior on failure:**
1. Log a warning message with the exception
2. Continue execution (don't crash the app)
3. Still publish the branch status so the state reflects intent

---

## Entity Existence Checks

Before making service calls, the app checks if entities exist:

```python
def _entity_exists(self, entity_id: str) -> bool:
    if not entity_id:
        return False
    try:
        state = self.get_state(entity_id)
        return state is not None
    except Exception:
        return False
```

Service calls are only made if:
- The target entity exists (checked via `_entity_exists()`)
- The entity is readable/writable

**Warning behavior:** If critical entities (SOC sensor, price sensor) are missing, the entire cycle is skipped with a warning log.

---

## Service Call Frequency

| Trigger | Frequency | Service Calls |
|---|---|---|
| Regular cycle | Every 5 minutes | 1-2 service calls per cycle |
| Live input change | After debounce delay (2s) | 1-2 service calls |
| Input unchanged | N/A | No service calls (early return) |
| Startup | Once (30s delay) | Initial setpoint + status publish |

---

## Performance Considerations

- **Debounce delay**: Live input changes trigger a re-run after `rerun_debounce_s` (default 2 seconds), preventing rapid-fire service calls during slider drags
- **Timer cancellation**: If multiple inputs change rapidly, only the last change triggers a re-run (previous timers are cancelled)
- **Selective updates**: The strategy only switches modes when necessary (checks current strategy before calling `select/select_option`)

```python
# Only switch if not already on target strategy
current_strategy = self.get_state(self.strategy_select)
if current_strategy != "nom":
    self.call_service("select/select_option", ...)
```

---

## Complete Service Call Reference

### All Service Domains Used

| Domain | Service | Purpose | Frequency |
|---|---|---|---|
| `select` | `select_option` | Switch Sessy strategy | Medium |
| `number` | `set_value` | Set power setpoints | Medium |
| (AppDaemon internal) | `set_state` | Update status sensor | High |

### Service Call Parameters

**`select/select_option`:**
```yaml
domain: select
service: select_option
parameters:
  entity_id: <entity_id>  # select entity
  option: <string>       # option value
```

**`number/set_value`:**
```yaml
domain: number
service: set_value
parameters:
  entity_id: <entity_id>  # number entity
  value: <int>          # integer value
```

**`set_state` (AppDaemon):**
```yaml
domain: (internal)
service: set_state
parameters:
  entity_id: <entity_id>  # sensor entity
  state: <string>        # state value
  attributes: <dict>     # attribute dictionary
```

---

## See Also

- [Entity Reference](entity-reference.md) — Entities targeted by these services
- [Architecture](architecture.md) — AppDaemon lifecycle and callbacks
- [Live Tuning Entities](live-tuning-entities.md) — Triggers for immediate re-runs
- [Override Manual Mode](../../how-to/override-manual-mode.md) — Using manual setpoint modes
