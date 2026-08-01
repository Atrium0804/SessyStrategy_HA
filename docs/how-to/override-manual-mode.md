---
title: Override Manual Mode
doc_type: how-to
problem: "I need to force a setpoint or take manual control"
solution: "Use manual modes to override the automatic strategy temporarily"
audience: users
tags:
  - manual control
  - override
  - setpoint
  - troubleshooting
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Override Manual Mode

**Problem:** You need to temporarily force a specific battery or grid setpoint, bypassing the automatic price-optimization strategy.

**Solution:** Use one of the manual operating modes (`grid_setpoint` or `battery_setpoint`) to directly control your Sessy system, either through a master mode selector or by setting a manual setpoint value.

---

## Related Documentation

- [Setpoint Types Explained](../explanation/setpoint-types-explained.md)
- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [Entity Reference](../reference/entity-reference.md)
- [Live Tuning Entities](../reference/live-tuning-entities.md)

---

## Understanding Manual Modes

### The Operating Mode Hierarchy

SessyStrategy supports multiple operating modes, controlled through a master `mode_select` entity. The strategy evaluates the mode first, before running any price-optimization logic.

| Mode | Behavior | Setpoint Type | When to Use |
|------|----------|---------------|-------------|
| `optimized` | Full automatic price optimization | Varies by priority | Normal operation |
| `grid_setpoint` | Manual grid target control | Grid setpoint (NOM) | Control grid import/export directly |
| `battery_setpoint` | Manual battery power control | Battery setpoint (API) | Control battery charge/discharge directly |
| `sessy_dynamic` | Hand control to Sessy | Sessy's own strategy | Use Sessy's built-in scheduling |
| `eco` | Eco mode | Sessy's eco strategy | Energy-saving mode |
| `idle` | Idle mode | None | Park the battery, no action |

### Manual Mode Flow

```
mode_select → [grid_setpoint | battery_setpoint] 
    → setpoint_entity value → [grid target | battery power]
```

The strategy reads from your configured `setpoint_entity` and writes to the appropriate target based on the mode.

---

## Solution Steps

### Step 1: Choose Your Manual Mode Method

You have three ways to implement manual control:

#### Method A: Master Mode Selector Only

Use the `mode_select` entity to switch between modes, with a single `setpoint_entity` for manual setpoints.

**Best for:** Users who want to switch between automatic and manual modes using a single selector.

#### Method B: Dedicated Manual Entities

Set up separate entities for different manual control scenarios.

**Best for:** Users who want predefined manual setpoints (e.g., "Max Discharge", "Force Charge").

#### Method C: Hybrid (Recommended)

Use mode selector for mode switching and a live setpoint entity for dynamic values.

**Best for:** Most users — combines flexibility with ease of use.

### Step 2: Configure Your Mode Selector

The `mode_select` entity is the master control for SessyStrategy.

**What to do:** Set up an input_select entity with all the modes you want to use.

**How to do it:**

1. **Create an input_select helper in Home Assistant:**
   - Go to **Settings > Devices & Services > Helpers**
   - Click **Add Helper** and select **Input Select**
   - Configure as follows:

   ```yaml
   # Created via UI, equivalent YAML:
   input_select:
     home_battery_mode:
       name: "Home Battery Mode"
       options:
         - optimized
         - grid_setpoint
         - battery_setpoint
         - sessy_dynamic
         - eco
         - idle
       initial: optimized
   ```

2. **Configure in apps.yaml:**
   ```yaml
   sessy_strategy:
     module: sessy_strategy
     class: SessyStrategy
     mode_select: select.home_battery_mode  # Your mode selector entity
   ```

**Note:** Mode names are case-insensitive and spaces are automatically converted to underscores. For example, "Grid Setpoint" becomes `grid_setpoint`.

### Step 3: Configure Your Setpoint Entity

The `setpoint_entity` is where you specify the actual power value when in manual modes.

**What to do:** Set up an input_number entity for your manual setpoint.

**How to do it:**

1. **Create an input_number helper:**
   - Go to **Settings > Devices & Services > Helpers**
   - Click **Add Helper** and select **Input Number**
   - Configure as follows:

   | Property | Value | Notes |
   |----------|-------|-------|
   | Name | Home Battery Setpoint | Display name |
   | Entity ID | `number.home_battery_setpoint` | Must match apps.yaml |
   | Min | -3500 | Should match your max_power_w negative |
   | Max | 3500 | Should match your max_power_w |
   | Step | 50 | Or 100 for coarser control |
   | Unit | W | Watts |
   | Initial | 0 | Default to no action |
   | Mode | box | Allows slider or direct input |

2. **Configure in apps.yaml:**
   ```yaml
   sessy_strategy:
     module: sessy_strategy
     class: SessyStrategy
     mode_select: select.home_battery_mode
     setpoint_entity: number.home_battery_setpoint
     
     # Optional: Sessy power_strategy option strings
     # These are used when handing control back to Sessy
     sessy_dynamic_option: roi  # Default for ha-sessy
     eco_option: eco
     idle_option: idle
   ```

**Expected result:** When in `grid_setpoint` or `battery_setpoint` mode, the value from `number.home_battery_setpoint` will be applied to the appropriate target.

### Step 4: Understand What Each Manual Mode Does

#### Mode: grid_setpoint

**What it does:** 
- Switches Sessy to **NOM** (nominal) strategy
- Sets the `grid_target` entity to your specified setpoint value
- Positive values = import from grid
- Negative values = export to grid
- Battery handles the rest automatically

**Use cases:**
- Force import during very cheap hours
- Force export during very expensive hours
- Balance grid interaction regardless of battery state

**Example:**
- Setpoint: `1000` → Import 1000W from grid
- Setpoint: `-1000` → Export 1000W to grid
- Setpoint: `0` → No grid interaction (default behavior)

**Log output:**
```
MANUAL grid setpoint 1000W
Strategy → nom (grid setpoint)
```

#### Mode: battery_setpoint

**What it does:**
- Switches Sessy to **API** (battery) strategy
- Sets the `battery_setpoint` entity to your specified setpoint value
- Positive values = discharge battery
- Negative values = charge battery
- Grid interaction is automatic

**Use cases:**
- Force battery to charge at specific rate
- Force battery to discharge at specific rate
- Test battery performance
- Emergency battery management

**Example:**
- Setpoint: `2000` → Discharge battery at 2000W
- Setpoint: `-2000` → Charge battery at 2000W
- Setpoint: `0` → No battery action

**Log output:**
```
MANUAL battery setpoint -2000W
Strategy → api (battery setpoint)
```

### Step 5: Create a Dashboard for Easy Control

Set up a Home Assistant dashboard to make manual mode switching easy.

**Example Lovelace card configuration:**

```yaml
# Mode selector card
- type: entities
  title: Battery Mode Control
  entities:
    - entity: select.home_battery_mode
      name: Operating Mode
    - entity: number.home_battery_setpoint
      name: Manual Setpoint
    - entity: sensor.sessy_strategy_status
      name: Current Strategy
```

**Example with conditional visibility:**

```yaml
# Show manual setpoint only when in manual mode
- type: conditional
  conditions:
    - entity: select.home_battery_mode
      state: grid_setpoint
    - entity: select.home_battery_mode
      state: battery_setpoint
  card:
    type: entity
    entity: number.home_battery_setpoint
```

**Example with quick action buttons:**

```yaml
# Quick action buttons for common manual operations
- type: button
  name: Max Discharge
  tap_action:
    action: call-service
    service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: battery_setpoint
  hold_action:
    action: call-service
    service: number.set_value
    target:
      entity_id: number.home_battery_setpoint
    data:
      value: 2200

- type: button
  name: Max Charge
  tap_action:
    action: call-service
    service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: battery_setpoint
  hold_action:
    action: call-service
    service: number.set_value
    target:
      entity_id: number.home_battery_setpoint
    data:
      value: -2200

- type: button
  name: Return to Auto
  tap_action:
    action: call-service
    service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: optimized
```

---

## Verification

To confirm your manual mode setup is working:

1. **Check current mode in status sensor:**
   - Look at `sensor.sessy_strategy_status` state
   - Should show `manual_grid` or `manual_battery` when in manual modes

2. **Review the logs:**
   ```
   # When switching to grid_setpoint mode:
   MANUAL grid setpoint 1000W
   Strategy → nom (grid setpoint)
   
   # When switching to battery_setpoint mode:
   MANUAL battery setpoint -1500W
   Strategy → api (battery setpoint)
   ```

3. **Verify entity changes:**
   - In `grid_setpoint` mode: Check `number.sessy_pwkn_grid_target` (or your configured grid_target)
   - In `battery_setpoint` mode: Check `number.sessy_battery_alt9_power_setpoint` (or your configured battery_setpoint)

4. **Test behavior:**
   - Set mode to `grid_setpoint` with setpoint of `-500`
   - Verify grid exports 500W
   - Set mode to `battery_setpoint` with setpoint of `1000`
   - Verify battery discharges at 1000W
   - Set mode back to `optimized`
   - Verify automatic strategy resumes

---

## Common Issues

### Issue 1: Manual Mode Not Working

**Symptom:** Strategy stays in optimized mode even when mode_select is changed.

**Cause:**
- `mode_select` entity ID is incorrect in apps.yaml
- Entity doesn't exist or has wrong options
- AppDaemon hasn't been restarted after configuration changes

**Fix:**
1. Verify entity ID matches exactly:
   ```yaml
   mode_select: select.home_battery_mode  # Must match your entity
   ```
2. Check entity exists in Home Assistant
3. Verify entity has correct options (optimized, grid_setpoint, battery_setpoint, etc.)
4. Restart AppDaemon
5. Check AppDaemon logs for mode detection messages

### Issue 2: Setpoint Not Applied

**Symptom:** Manual setpoint value is ignored.

**Cause:**
- `setpoint_entity` is not configured
- Setpoint entity doesn't exist
- Mode is not `grid_setpoint` or `battery_setpoint`
- Value is outside allowed range

**Fix:**
1. Verify `setpoint_entity` is configured:
   ```yaml
   setpoint_entity: number.home_battery_setpoint
   ```
2. Check entity exists and has correct min/max values
3. Ensure mode is set to `grid_setpoint` or `battery_setpoint`
4. Check that setpoint value is within your battery's capabilities

### Issue 3: Wrong Setpoint Type Applied

**Symptom:** Grid setpoint applied when you wanted battery setpoint, or vice versa.

**Cause:**
- Mode is set incorrectly
- Entity configuration is wrong

**Fix:**
1. Verify current mode in status sensor
2. Check mode_select entity state
3. If in `grid_setpoint` mode but want battery control, switch to `battery_setpoint`
4. If in `battery_setpoint` mode but want grid control, switch to `grid_setpoint`

### Issue 4: Automatic Strategy Doesn't Resume

**Symptom:** Strategy stays in manual mode even after switching back to optimized.

**Cause:**
- The strategy is still processing the manual mode
- There's a delay in mode switching

**Fix:**
1. Wait for the next strategy cycle (5 minutes)
2. Force an immediate recalculation by changing any live input
3. Restart AppDaemon if needed
4. Check that `mode_select` entity actually shows "optimized"

---

## Alternative Approaches

### Approach 1: Multiple Mode Selectors

**Use case:** Different mode selectors for different scenarios.

**Pros:**
- Flexible control
- Can have specialized selectors

**Cons:**
- More complex configuration
- Can be confusing

**Implementation:**
```yaml
# Primary mode selector
mode_select: select.home_battery_mode

# Secondary selector for specific scenarios
# (Would require custom app logic to handle)
```

### Approach 2: Automated Mode Switching

**Use case:** Automatically switch to manual mode under specific conditions.

**Pros:**
- Hands-off automatic switching
- Can respond to external events

**Cons:**
- More complex setup
- Requires automation knowledge

**Implementation:**
```yaml
# Example: Switch to battery_setpoint during grid outage
alias: "Grid Outage Manual Mode"
trigger:
  - platform: state
    entity_id: binary_sensor.grid_power_available
    to: "off"
action:
  - service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: battery_setpoint
  - service: number.set_value
    target:
      entity_id: number.home_battery_setpoint
    data:
      value: -2000  # Max charge to store energy

# Return to optimized when grid returns
alias: "Grid Restored Auto Mode"
trigger:
  - platform: state
    entity_id: binary_sensor.grid_power_available
    to: "on"
    for: 00:05:00  # Wait 5 minutes for stability
action:
  - service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: optimized
```

### Approach 3: Predefined Setpoint Buttons

**Use case:** Quick access to common setpoint values.

**Pros:**
- Simple one-click control
- Good for mobile dashboards

**Cons:**
- Limited flexibility
- Requires more dashboard space

**Implementation:**
Create multiple input_number entities with fixed values, then use scripts to set both mode and setpoint:

```yaml
# Script to set max discharge
alias: "Set Max Discharge"
sequence:
  - service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: battery_setpoint
  - service: number.set_value
    target:
      entity_id: number.home_battery_setpoint
    data:
      value: 2200

# Script to set max charge
alias: "Set Max Charge"
sequence:
  - service: select.select_option
    target:
      entity_id: select.home_battery_mode
    data:
      option: battery_setpoint
  - service: number.set_value
    target:
      entity_id: number.home_battery_setpoint
    data:
      value: -2200
```

---

## Best Practices

- [x] **Do:** Start with the hybrid approach (mode selector + setpoint entity)
- [x] **Do:** Use the same max/min values for your setpoint entity as your battery's capabilities
- [x] **Do:** Test manual modes during low-usage periods first
- [x] **Do:** Monitor battery behavior closely when in manual mode
- [x] **Do:** Return to `optimized` mode when manual control is no longer needed
- ❌ **Don't:** Leave manual modes active for extended periods without monitoring
- ❌ **Don't:** Set setpoints outside your battery's rated capacity
- ❌ **Don't:** Switch modes rapidly — allow time for the strategy to process
- ❌ **Don't:** Use manual modes as a permanent solution — optimize your configuration instead

---

## See Also

- [Setpoint Types Explained](../explanation/setpoint-types-explained.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [How to Debug Strategy Decisions](../how-to/debug-strategy-decisions.md)
- [How to Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)

---

## Quick Checklist

- [ ] Set up mode_select input_select entity with all required modes
- [ ] Configured mode_select entity ID in apps.yaml
- [ ] Set up setpoint_entity input_number with appropriate range
- [ ] Configured setpoint_entity in apps.yaml
- [ ] Tested grid_setpoint mode with positive and negative values
- [ ] Tested battery_setpoint mode with positive and negative values
- [ ] Verified return to optimized mode works
- [ ] Created dashboard for easy mode switching
- [ ] Tested quick action buttons or scripts (if using)

---

*Last updated: 2026-08-01*