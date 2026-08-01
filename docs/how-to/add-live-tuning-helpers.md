---
title: Add Live Tuning Helpers
doc_type: how-to
problem: "I want to tweak parameters without restarting AppDaemon"
solution: "Create input_number entities that the strategy reads each cycle"
audience: users
tags:
  - live tuning
  - configuration
  - dashboard
  - no restart
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Add Live Tuning Helpers

**Problem:** You want to adjust SessyStrategy parameters (like price thresholds, SOC targets, etc.) from your Home Assistant dashboard without editing `apps.yaml` and restarting AppDaemon.

**Solution:** Create Home Assistant input_number entities and link them to the strategy's live tuning parameters. The strategy reads these values each cycle, so changes take effect immediately (after a short debounce delay).

---

## 📚 Related Documentation

- [Live Tuning Entities Reference](../reference/live-tuning-entities.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [How to Tune Price Thresholds](../how-to/tune-price-thresholds.md)

---

## 🎯 Understanding Live Tuning

### What Live Tuning Does

Live tuning allows you to:
- **Adjust parameters in real-time** from Home Assistant UI
- **Experiment with different values** without editing configuration files
- **Temporarily override** static values for testing
- **Automate parameter changes** based on conditions

### How It Works

1. **You create** input_number (or input_select) entities in Home Assistant
2. **You link** these entities to the strategy via `_entity` configuration parameters
3. **Each cycle**, the strategy checks the entity values using the `_tunable()` helper
4. **If the entity exists and is readable**, it uses the live value
5. **If not**, it falls back to the static value from `apps.yaml`
6. **Changes trigger** an immediate re-run (after `rerun_debounce_s` delay, default 2 seconds)

### Supported Live Tuning Parameters

SessyStrategy supports live tuning for these parameters:

| Parameter | Entity Type | Purpose | Default Static Value |
|-----------|-------------|---------|---------------------|
| `soc_target_entity` | input_number | Target SOC for pre-peak charging | `soc_target: 70` |
| `soc_floor_entity` | input_number | Minimum SOC — never discharge below | `soc_floor: 0` |
| `cheap_soc_target_entity` | input_number | Maximum SOC for cheap-price charging | `cheap_soc_target: 100` |
| `price_discharge_entity` | input_number | Raw price threshold for discharging | `price_discharge: 0.39` |
| `price_charge_entity` | input_number | Raw price threshold for charging | `price_charge: -0.10` |
| `min_arbitrage_margin_entity` | input_number | Minimum price spread for pre-peak charging | `min_arbitrage_margin: 0.05` |
| `season_mode_entity` | input_select | Live season mode override | `season_mode: auto` |

**Note:** The `mode_select` entity is also live-tuned and controls the operating mode.

### Fallback Behavior

The strategy always falls back gracefully:
```
If entity exists AND is readable → Use entity value
Else → Use static value from apps.yaml
```

---

## ✅ Solution Steps

### Step 1: Plan Your Live Tuning Setup

Decide which parameters you want to make adjustable:

**Essential (Recommended for all users):**
- `price_discharge_entity` — Adjust when to sell energy
- `price_charge_entity` — Adjust when to buy energy
- `soc_target_entity` — Adjust target SOC for pre-peak

**Useful for optimization:**
- `soc_floor_entity` — Adjust minimum SOC
- `cheap_soc_target_entity` — Adjust cheap charge ceiling
- `min_arbitrage_margin_entity` — Adjust pre-peak spread requirement

**Seasonal control:**
- `season_mode_entity` — Switch between summer/winter/auto

### Step 2: Create Input Number Entities

For each parameter you want to live-tune, create an input_number helper.

**What to do:** Create input_number entities in Home Assistant.

**How to do it:**

1. Go to **Settings > Devices & Services > Helpers**
2. Click **Add Helper** and select **Input Number**
3. Create entities with these configurations:

#### SOC Target (for pre-peak charging)
```yaml
# Input Number Helper Configuration
name: "SOC Target"
entity_id: number.home_battery_soc_target
min: 0
max: 100
step: 1
unit: "%"
initial: 70  # Match your static value
mode: box
```

#### SOC Floor (minimum SOC)
```yaml
name: "SOC Floor"
entity_id: number.home_battery_soc_floor
min: 0
max: 100
step: 1
unit: "%"
initial: 0  # Match your static value
mode: box
```

#### Cheap SOC Target (for cheap price charging)
```yaml
name: "Cheap SOC Target"
entity_id: number.home_battery_soc_ceiling
min: 0
max: 100
step: 1
unit: "%"
initial: 100  # Match your static value
mode: box
```

#### Price Discharge Threshold
```yaml
name: "Price Discharge"
entity_id: number.home_battery_price_discharge
min: -1.0
max: 2.0
step: 0.01
unit: "€/kWh"
initial: 0.39  # Match your static value
mode: box
```

#### Price Charge Threshold
```yaml
name: "Price Charge"
entity_id: number.home_battery_price_charge
min: -1.0
max: 1.0
step: 0.01
unit: "€/kWh"
initial: -0.10  # Match your static value
mode: box
```

#### Minimum Arbitrage Margin
```yaml
name: "Min Arbitrage Margin"
entity_id: number.home_battery_min_arbitrage_margin
min: 0.0
max: 0.5
step: 0.01
unit: "€/kWh"
initial: 0.05  # Match your static value
mode: box
```

### Step 3: Create Season Mode Entity (Optional)

If you want live control over season mode:

```yaml
# Input Select Helper Configuration
name: "Sessy Season Mode"
entity_id: input_select.sessy_season_mode
options:
  - auto
  - summer
  - winter
initial: auto
```

### Step 4: Link Entities to Strategy

**What to do:** Configure the entity links in your `apps.yaml`.

**How to do it:**

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  
  # Static fallback values (used if entities unavailable)
  soc_target: 70
  soc_floor: 0
  cheap_soc_target: 100
  price_discharge: 0.39
  price_charge: -0.10
  min_arbitrage_margin: 0.05
  season_mode: auto
  
  # Live entity overrides
  soc_target_entity: number.home_battery_soc_target
  soc_floor_entity: number.home_battery_soc_floor
  cheap_soc_target_entity: number.home_battery_soc_ceiling
  price_discharge_entity: number.home_battery_price_discharge
  price_charge_entity: number.home_battery_price_charge
  min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
  season_mode_entity: input_select.sessy_season_mode
```

**Expected result:** Restart AppDaemon, and the strategy will now read from your entities each cycle.

### Step 5: Configure Debounce Delay (Optional)

The strategy waits a short time after entity changes to allow slider drags to complete before re-running.

**Default:** `rerun_debounce_s: 2.0` (2 seconds)

**Adjust if needed:**
```yaml
sessy_strategy:
  rerun_debounce_s: 1.0  # Faster response (1 second)
  # Or
  rerun_debounce_s: 3.0  # Slower response (3 seconds)
```

**Recommendations:**
- **1-2 seconds**: Good for most use cases
- **3-5 seconds**: If you have slow systems or network latency
- **0.5 seconds**: For very responsive systems (but may cause more frequent re-runs)

### Step 6: Create a Live Tuning Dashboard

Set up a dedicated dashboard for tuning your strategy.

**Example Lovelace card configuration:**

```yaml
# Live Tuning Dashboard
- type: vertical-stack
  cards:
    # Price Thresholds Section
    - type: markdown
      content: "### 💰 Price Thresholds"
    
    - type: horizontal-stack
      cards:
        - type: entity
          entity: number.home_battery_price_discharge
          name: Discharge Threshold
          icon: mdi:export
        
        - type: entity
          entity: number.home_battery_price_charge
          name: Charge Threshold
          icon: mdi:import
    
    - type: entity
      entity: number.home_battery_min_arbitrage_margin
      name: Arbitrage Margin
      icon: mdi:margin
    
    # SOC Targets Section
    - type: markdown
      content: "### 🔋 SOC Targets"
    
    - type: horizontal-stack
      cards:
        - type: entity
          entity: number.home_battery_soc_target
          name: Pre-Peak Target
          icon: mdi:target
        
        - type: entity
          entity: number.home_battery_soc_floor
          name: Minimum SOC
          icon: mdi:floor
        
        - type: entity
          entity: number.home_battery_soc_ceiling
          name: Cheap Charge Ceiling
          icon: mdi:ceiling
    
    # Season Mode Section
    - type: markdown
      content: "### 🌞 Season Mode"
    
    - type: entity
      entity: input_select.sessy_season_mode
      name: Season Mode
      icon: mdi:weather-seasons
    
    # Current Status Section
    - type: markdown
      content: "### 📊 Current Status"
    
    - type: entity
      entity: sensor.sessy_strategy_status
      name: Strategy Status
      secondary_info: last-changed
```

**Advanced dashboard with conditional visibility:**

```yaml
# Show only relevant controls based on current mode
- type: conditional
  conditions:
    - entity: select.home_battery_mode
      state: optimized
  card:
    type: vertical-stack
    cards:
      - type: entity
        entity: number.home_battery_price_discharge
      - type: entity
        entity: number.home_battery_price_charge
      - type: entity
        entity: number.home_battery_soc_target
      # ... other live tuning controls
```

---

## 🔍 Verification

To confirm your live tuning setup is working:

1. **Check entity values in status sensor:**
   - Look at `sensor.sessy_strategy_status` attributes
   - Verify the values match your entity inputs:
     - `soc_target` should match `number.home_battery_soc_target`
     - `price_discharge` should match `number.home_battery_price_discharge`
     - `price_charge` should match `number.home_battery_price_charge`
     - etc.

2. **Test live changes:**
   - Change `number.home_battery_price_discharge` from 0.39 to 0.45
   - Wait 2 seconds (or your configured debounce delay)
   - Check AppDaemon logs for:
     ```
     Input select.home_battery_mode changed auto → auto — re-running in 2s
     # Or for price changes:
     Input number.home_battery_price_discharge changed 0.39 → 0.45 — re-running in 2s
     ```
   - Verify the status sensor shows the new value

3. **Test strategy behavior:**
   - Lower `price_discharge` to trigger discharge at lower prices
   - Verify strategy enters Priority 1 (discharge) when raw price exceeds new threshold
   - Raise `price_charge` to trigger charging at higher prices
   - Verify strategy enters Priority 2 (cheap charge) when raw price drops below new threshold

4. **Test fallback behavior:**
   - Temporarily disable an entity (set to unavailable in Home Assistant)
   - Verify the strategy falls back to the static value from `apps.yaml`

---

## ⚠️ Common Issues

### Issue 1: Live Entities Not Working

**Symptom:** Changing entity values doesn't affect strategy behavior.

**Cause:**
- Entity IDs don't match between Home Assistant and apps.yaml
- Entities don't exist or have wrong types
- AppDaemon hasn't been restarted after configuration changes
- Entities are not readable by AppDaemon

**Fix:**
1. Verify entity IDs match exactly:
   ```yaml
   # apps.yaml
   price_discharge_entity: number.home_battery_price_discharge
   
   # Home Assistant entity must be:
   # entity_id: number.home_battery_price_discharge
   ```
2. Check entities exist and are available
3. Restart AppDaemon
4. Check AppDaemon logs for entity reading errors

### Issue 2: Changes Take Too Long to Apply

**Symptom:** Strategy doesn't respond immediately to entity changes.

**Cause:**
- `rerun_debounce_s` is set too high
- Network latency between Home Assistant and AppDaemon
- Slow system performance

**Fix:**
1. Reduce debounce delay:
   ```yaml
   rerun_debounce_s: 1.0  # Faster response
   ```
2. Check system performance — slow systems may need optimization
3. Verify AppDaemon and Home Assistant are running on the same machine or have good connectivity

### Issue 3: Strategy Re-runs Too Frequently

**Symptom:** Strategy re-runs constantly, causing excessive logging.

**Cause:**
- `rerun_debounce_s` is set too low
- Entity values are fluctuating (e.g., from automation)
- Multiple entities changing simultaneously

**Fix:**
1. Increase debounce delay:
   ```yaml
   rerun_debounce_s: 3.0  # Slower response
   ```
2. Check for automation loops that might be changing entities repeatedly
3. Consider using Home Assistant automations with delays instead of immediate changes

### Issue 4: Entity Values Reset After Restart

**Symptom:** Live entity values reset to initial values after AppDaemon or Home Assistant restart.

**Cause:**
- This is expected behavior — input_number initial values are used
- The strategy doesn't persist entity states

**Fix:**
1. **Option A:** Accept this as normal behavior and reconfigure after restarts
2. **Option B:** Use input_number with `initial` values matching your desired defaults
3. **Option C:** Create a script to restore entity values after restart:
   ```yaml
   # Automation to restore live tuning values on startup
   alias: "Restore Live Tuning Values"
   trigger:
     - platform: homeassistant
       event: start
   action:
     - service: number.set_value
       target:
         entity_id: number.home_battery_price_discharge
       data:
         value: 0.39
     - service: number.set_value
       target:
         entity_id: number.home_battery_price_charge
       data:
         value: -0.10
     # ... restore other values
   ```

---

## 🎯 Advanced Usage

### Automated Tuning Based on Conditions

Use Home Assistant automations to adjust parameters based on external conditions.

**Example: Increase SOC floor during winter**
```yaml
alias: "Winter SOC Floor Adjustment"
trigger:
  - platform: state
    entity_id: input_select.sessy_season_mode
    to: winter
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_soc_floor
    data:
      value: 10  # Higher floor in winter

alias: "Summer SOC Floor Adjustment"
trigger:
  - platform: state
    entity_id: input_select.sessy_season_mode
    to: summer
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_soc_floor
    data:
      value: 0  # Lower floor in summer
```

**Example: Adjust thresholds based on time of day**
```yaml
# More aggressive discharge during evening peak
alias: "Evening Peak Discharge"
trigger:
  - platform: time
    at: "18:00:00"
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_price_discharge
    data:
      value: 0.35  # Lower threshold for evening

# Return to normal in morning
alias: "Morning Normal Thresholds"
trigger:
  - platform: time
    at: "06:00:00"
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_price_discharge
    data:
      value: 0.39  # Normal threshold
```

**Example: Emergency backup mode**
```yaml
alias: "Emergency Backup Mode"
trigger:
  - platform: state
    entity_id: binary_sensor.grid_power_available
    to: "off"
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_soc_floor
    data:
      value: 90  # Keep battery charged
  - service: number.set_value
    target:
      entity_id: number.home_battery_price_discharge
    data:
      value: 10.00  # Only discharge at extremely high prices
```

### Integration with External Systems

**Example: Adjust thresholds based on weather forecast**
```yaml
# Charge more aggressively when sunny forecast (more solar generation)
alias: "Sunny Day Charging"
trigger:
  - platform: numeric_state
    entity_id: sensor.solar_forecast_tomorrow
    above: 8  # kWh forecast
condition:
  - condition: time
    after: "06:00:00"
    before: "12:00:00"
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_price_charge
    data:
      value: -0.05  # More aggressive charging
```

**Example: Adjust based on energy provider notifications**
```yaml
# Respond to critical peak notifications
alias: "Critical Peak Response"
trigger:
  - platform: state
    entity_id: binary_sensor.critical_peak_alert
    to: "on"
action:
  - service: number.set_value
    target:
      entity_id: number.home_battery_price_discharge
    data:
      value: 0.25  # Discharge at lower threshold during critical peak
```

---

## 📝 Best Practices

- ✅ **Do:** Start with the essential parameters (price thresholds, SOC targets)
- ✅ **Do:** Use descriptive names for your entities
- ✅ **Do:** Set initial values to match your static configuration
- ✅ **Do:** Use appropriate min/max/step values for each parameter
- ✅ **Do:** Test live changes during low-usage periods first
- ✅ **Do:** Monitor strategy behavior after changes
- ✅ **Do:** Use automations to adjust parameters based on conditions
- ❌ **Don't:** Create entities for parameters you never change
- ❌ **Don't:** Set debounce delay too low (can cause excessive re-runs)
- ❌ **Don't:** Remove entity configurations from apps.yaml after setting up live entities
- ❌ **Don't:** Expect live entity changes to persist across restarts

---

## 🔗 See Also

- [Live Tuning Entities Reference](../reference/live-tuning-entities.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [How to Tune Price Thresholds](../how-to/tune-price-thresholds.md)
- [How to Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)
- [How to Override Manual Mode](../how-to/override-manual-mode.md)

---

## 📊 Quick Checklist

- [ ] Identified which parameters to make live-tunable
- [ ] Created input_number entities for each parameter
- [ ] Set appropriate min/max/step/initial values for each entity
- [ ] Created input_select for season mode (if using)
- [ ] Configured entity links in apps.yaml
- [ ] Set appropriate rerun_debounce_s value
- [ ] Restarted AppDaemon
- [ ] Verified entities appear in status sensor
- [ ] Tested live changes and verified immediate effect
- [ ] Tested fallback to static values
- [ ] Created dashboard for easy access
- [ ] Set up advanced automations (if needed)

---

*Last updated: 2026-08-01*