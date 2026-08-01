---
title: Migrate from Older Version
doc_type: how-to
problem: "I'm upgrading from an older version of SessyStrategy"
solution: "Understand breaking changes, migrate configuration, and validate the upgrade"
audience: users
tags:
  - migration
  - upgrade
  - breaking changes
  - compatibility
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Migrate from Older Version

**Problem:** You're upgrading from an older version of SessyStrategy HA and need to ensure your configuration, entities, and expected behavior work with the new version.

**Solution:** Follow this migration guide to understand what's changed, update your configuration, test the upgrade, and roll back if needed. This guide covers migrations from various previous versions to the current release.

---

## Related Documentation

- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [Entity Reference](../reference/entity-reference.md)
- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [Changelog / Commit History](https://github.com/your-repo/SessyStrategy_HA/commits/) (if available)

---

## Version History and Breaking Changes

### Version Identification

| Version | File | Key Changes | Release Date |
|---------|------|-------------|--------------|
| **Current** | `sessy_strategy.py` v3.x | Full priority chain, live tuning, seasonal mode | 2026-07-01 |
| **v2.1** | `sessy_strategy.py` v2.1 | Basic priority chain, fixed thresholds | 2026-03-01 |
| **v2.0** | `sessy_strategy.py` v2.0 | Initial AppDaemon implementation | 2026-01-01 |
| **v1.x** | Legacy scripts | Manual setpoint management | Pre-2026 |

**How to check your current version:**
1. Look at the top of `sessy_strategy.py` for version comments
2. Check the git commit hash or tag
3. Review the feature set in your current configuration

### Breaking Changes by Version

#### From v2.1 to v3.x (Current)

**Major changes:**
- [x] **New**: Seasonal mode support (`auto`, `summer`, `winter`)
- [x] **New**: Live tuning entities for all major parameters
- [x] **New**: Adaptive spread windows for charge/discharge
- [x] **New**: Priority 4 — Evening peak excess discharge
- [x] **New**: Pre-peak arbitrage margin check

[!warning]
The following changes require attention:
- **Changed**: Price threshold logic now uses raw prices exclusively
- **Changed**: SOC target for pre-peak is separate from cheap charge
- **Changed**: `min_window_h` parameter added for adaptive spreading
- **Changed**: `rerun_debounce_s` parameter added for live input handling
- **Changed**: Entity naming convention standardized

**Configuration changes required:**

```yaml
# OLD v2.1 configuration
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  battery_capacity: 5000
  max_power: 2200
  soc_target: 90
  soc_min: 20
  soc_max: 100
  price_high: 0.50  # This was IMPORT price
  price_low: 0.10   # This was IMPORT price
  
# NEW v3.x configuration
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  capacity_wh: 5000        # Renamed from battery_capacity
  max_power_w: 2200        # Renamed from max_power
  soc_target: 70           # Changed default, now pre-peak target
  soc_floor: 0            # Renamed from soc_min
  cheap_soc_target: 100    # Renamed from soc_max
  price_discharge: 0.39    # NOW RAW price (was 0.50 import)
  price_charge: -0.10      # NOW RAW price (was 0.10 import)
  surcharge: 0.11          # NEW: import = raw + surcharge
  min_window_h: 2.0        # NEW: adaptive spread window
  rerun_debounce_s: 2.0    # NEW: live input debounce
```

**Critical conversion:**
```
# OLD: price_high = 0.50 (import price)
# NEW: price_discharge = 0.50 - 0.11 = 0.39 (raw price)

# OLD: price_low = 0.10 (import price)  
# NEW: price_charge = 0.10 - 0.11 = -0.01 (raw price)
```

#### From v2.0 to v3.x

**Changes:**
- All v2.1 changes (above)
- **Additional**: v2.0 used single SOC target, v3.x has separate targets

**Configuration migration:**

```yaml
# OLD v2.0 configuration
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  battery_size: 5000
  inverter_power: 2200
  target_soc: 80
  min_soc: 10
  high_price: 0.45
  low_price: 0.05
  
# NEW v3.x configuration  
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  capacity_wh: 5000
  max_power_w: 2200
  soc_target: 70           # Pre-peak target
  soc_floor: 10           # Minimum SOC
  cheap_soc_target: 90     # Cheap charge ceiling (was target_soc)
  price_discharge: 0.34    # high_price - surcharge
  price_charge: -0.06      # low_price - surcharge
  surcharge: 0.11
```

#### From v1.x (Legacy) to v3.x

**Changes:**
- Complete rewrite from scripts to AppDaemon app
- New entity structure
- New configuration format
- New priority chain logic

**Migration approach:**
1. **Start fresh** with new configuration
2. **Map old concepts** to new parameters
3. **Test thoroughly** before relying on automatic operation

---

## Migration Steps

### Step 1: Backup Your Current Configuration

**What to do:** Create backups of all current files and settings.

**How to do it:**

```bash
# Backup your apps.yaml
cp /config/appdaemon/apps/apps.yaml /config/appdaemon/apps/apps.yaml.backup

# Backup your current strategy file
cp /config/appdaemon/apps/sessy_strategy.py /config/appdaemon/apps/sessy_strategy.py.backup

# Backup Home Assistant entities (if using YAML)
cp /config/configuration.yaml /config/configuration.yaml.backup
```

**Also backup:**
- Screenshots of your current dashboard
- Notes on your current thresholds and behavior
- Any custom automations that interact with the strategy

### Step 2: Identify Your Current Version

**What to do:** Determine which version you're currently running.

**How to do it:**

1. **Check the file header:**
   ```bash
   head -n 20 /config/appdaemon/apps/sessy_strategy.py
   ```

2. **Look for version indicators:**
   - Comments like `# Version 2.1` or `# v3.0`
   - Feature presence: seasonal mode, live tuning, adaptive windows
   - Parameter names: `battery_capacity` vs `capacity_wh`

3. **Check git history (if you have it):**
   ```bash
   cd /config/appdaemon/apps
   git log --oneline sessy_strategy.py | head -5
   ```

### Step 3: Update Configuration Files

#### If upgrading from v2.1 to v3.x:

1. **Update parameter names:**
   ```yaml
   # In apps.yaml, change:
   battery_capacity: 5000  →  capacity_wh: 5000
   max_power: 2200        →  max_power_w: 2200
   soc_min: 20            →  soc_floor: 20
   soc_max: 100          →  cheap_soc_target: 100
   ```

2. **Convert price thresholds:**
   ```yaml
   # Assuming surcharge = 0.11 (Netherlands default)
   # OLD import prices → NEW raw prices
   price_high: 0.50  →  price_discharge: 0.39  # 0.50 - 0.11 = 0.39
   price_low: 0.10   →  price_charge: -0.01    # 0.10 - 0.11 = -0.01
   
   # Add surcharge parameter
   surcharge: 0.11
   ```

3. **Add new parameters with sensible defaults:**
   ```yaml
   min_window_h: 2.0
   rerun_debounce_s: 2.0
   prepeak_start: 15
   prepeak_end: 17
   prepeak_window_h: 2.0
   evening_peak_start: 18
   evening_peak_end: 23
   season_mode: auto
   season_day_start: 8
   season_day_end: 18
   season_auto_fallback: winter
   min_arbitrage_margin: 0.05
   ```

#### If upgrading from v2.0 or v1.x:

1. **Use the new configuration format:**
   - Start with the current `files/apps.yaml` as a template
   - Map your old parameters to new ones using the tables above

2. **Set appropriate defaults:**
   ```yaml
   # Start with these sensible defaults
   capacity_wh: 5000          # Your battery capacity
   max_power_w: 2200          # Your inverter max power
   soc_target: 70             # Pre-peak SOC target
   soc_floor: 0              # Minimum SOC
   cheap_soc_target: 100      # Cheap charge ceiling
   surcharge: 0.11            # Your import surcharge
   price_discharge: 0.39      # Discharge threshold (raw)
   price_charge: -0.10        # Charge threshold (raw)
   ```

### Step 4: Update Entity References

The entity naming convention has been standardized in v3.x.

**What to do:** Update your entity references if you're using non-standard names.

**Common entity changes:**

| Old Entity | New Entity | Notes |
|------------|------------|-------|
| `sensor.battery_soc` | `sensor.sessy_battery_alt9_state_of_charge` | Sessy integration standard |
| `sensor.energy_price` | `sensor.sessy_dnhh_energy_price` | Dynamic price sensor |
| `select.battery_strategy` | `select.sessy_battery_alt9_power_strategy` | Strategy selector |
| `number.grid_target` | `number.sessy_pwkn_grid_target` | Grid power target |
| `number.battery_setpoint` | `number.sessy_battery_alt9_power_setpoint` | Battery setpoint |

**If your entities have different names:**
```yaml
# In apps.yaml, override the defaults:
sessy_strategy:
  soc_sensor: sensor.your_battery_soc
  price_sensor: sensor.your_energy_price
  strategy_select: select.your_strategy
  grid_target: number.your_grid_target
  battery_setpoint: number.your_battery_setpoint
```

### Step 5: Add New Required Entities

v3.x requires a few more entities for full functionality:

**Required entities:**
- `soc_sensor` — Current battery SOC (must return numeric percentage)
- `price_sensor` — Current energy price with `energy_prices` attribute
- `strategy_select` — Sessy power strategy selector

**Optional but recommended:**
- `grid_target` — Grid power target (for grid setpoint mode)
- `battery_setpoint` — Battery power setpoint (for battery setpoint mode)

**What to do:** Ensure these entities exist in your Home Assistant.

**How to check:**
1. Go to **Developer Tools > States** in Home Assistant
2. Search for each entity ID from your configuration
3. Verify they exist and have valid states

**How to create missing entities:**
- Most entities come from the Sessy integration or your energy provider integration
- If missing, check your integrations and restart Home Assistant

### Step 6: Add Live Tuning Entities (Recommended)

v3.x supports live tuning — create entities for dynamic parameter adjustment:

```yaml
# Add to your configuration (or create via UI)
# SOC targets
number:
  - platform: input_number
    name: "SOC Target"
    entity_id: number.home_battery_soc_target
    min: 0
    max: 100
    step: 1
    unit: "%"
    initial: 70
    mode: box

  - platform: input_number
    name: "SOC Floor"
    entity_id: number.home_battery_soc_floor
    min: 0
    max: 100
    step: 1
    unit: "%"
    initial: 0
    mode: box

  - platform: input_number
    name: "Cheap SOC Target"
    entity_id: number.home_battery_soc_ceiling
    min: 0
    max: 100
    step: 1
    unit: "%"
    initial: 100
    mode: box

# Price thresholds
  - platform: input_number
    name: "Price Discharge"
    entity_id: number.home_battery_price_discharge
    min: -1.0
    max: 2.0
    step: 0.01
    unit: "€/kWh"
    initial: 0.39
    mode: box

  - platform: input_number
    name: "Price Charge"
    entity_id: number.home_battery_price_charge
    min: -1.0
    max: 1.0
    step: 0.01
    unit: "€/kWh"
    initial: -0.10
    mode: box

# Season mode
  - platform: input_select
    name: "Season Mode"
    entity_id: input_select.sessy_season_mode
    options:
      - auto
      - summer
      - winter
    initial: auto
```

Then link them in your apps.yaml:

```yaml
sessy_strategy:
  # ... other configuration ...
  soc_target_entity: number.home_battery_soc_target
  soc_floor_entity: number.home_battery_soc_floor
  cheap_soc_target_entity: number.home_battery_soc_ceiling
  price_discharge_entity: number.home_battery_price_discharge
  price_charge_entity: number.home_battery_price_charge
  season_mode_entity: input_select.sessy_season_mode
```

### Step 7: Test the Migration

**What to do:** Test the new version before relying on it for automatic operation.

**How to do it:**

1. **Restart AppDaemon:**
   ```bash
   appdaemon restart
   ```

2. **Check startup logs:**
   ```bash
   tail -n 20 /path/to/appdaemon.log | grep -i sessy
   ```
   Look for: `Sessy strategy starting up`

3. **Verify status sensor:**
   - Check `sensor.sessy_strategy_status` exists
   - Check it has all expected attributes
   - Verify `active_branch` shows a valid value

4. **Test each priority:**
   - **Priority 1:** Wait for high prices, verify discharge behavior
   - **Priority 2:** Wait for low/negative prices, verify charge behavior
   - **Priority 3:** Wait for pre-peak window, verify charge behavior
   - **Priority 4:** Wait for evening peak with excess SOC, verify discharge
   - **Priority 5:** Default behavior — grid setpoint 0W

5. **Test modes:**
   - Switch `mode_select` to `grid_setpoint`, verify grid target is set
   - Switch to `battery_setpoint`, verify battery setpoint is set
   - Switch back to `optimized`, verify automatic behavior resumes

6. **Test live tuning:**
   - Change a live entity value (e.g., `price_discharge`)
   - Wait 2 seconds for debounce
   - Verify the strategy re-runs with new value
   - Check status sensor shows updated value

### Step 8: Monitor and Validate

**What to do:** Run the new version for at least 24-48 hours to validate behavior.

**How to do it:**

1. **Compare behavior:**
   - Note when the strategy makes different decisions than your old version
   - Understand why (different thresholds, new logic, etc.)

2. **Monitor key metrics:**
   - Battery SOC over time
   - Grid import/export
   - Strategy decisions (from logs and status sensor)

3. **Check for issues:**
   - Excessive battery cycling
   - Missed charging/discharging opportunities
   - Unexpected mode switches

4. **Adjust configuration:**
   - Fine-tune thresholds based on observed behavior
   - Adjust SOC targets for your usage patterns
   - Optimize pre-peak windows for your energy prices

---

## Common Migration Issues

### Issue 1: Strategy Doesn't Start

**Symptom:** No logs from strategy, no status sensor created.

**Cause:**
- Missing required entities (`soc_sensor` or `price_sensor`)
- Configuration syntax errors in apps.yaml
- AppDaemon configuration issues

**Fix:**
1. Check AppDaemon logs for startup errors:
   ```bash
   tail -n 50 /path/to/appdaemon.log | grep -i error
   ```
2. Verify required entities exist:
   ```bash
   # Check SOC sensor
   curl -s "http://your-ha:8123/api/states/sensor.your_soc_sensor" | jq '.state'
   
   # Check price sensor
   curl -s "http://your-ha:8123/api/states/sensor.your_price_sensor" | jq '.state'
   ```
3. Validate YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('/path/to/apps.yaml'))"
   ```

### Issue 2: Wrong Price Basis (Raw vs Import)

**Symptom:** Strategy doesn't trigger at expected prices.

**Cause:**
- Old configuration used import prices, new version uses raw prices
- Surcharge not configured correctly

**Fix:**
1. **Understand the difference:**
   - Raw price: Export price (what you get for selling to grid)
   - Import price: Raw + surcharge (what you pay for buying from grid)

2. **Convert your thresholds:**
   ```
   # If you had import price thresholds:
   old_price_high = 0.50
   old_price_low = 0.10
   
   # Convert to raw prices:
   new_price_discharge = old_price_high - surcharge
   new_price_charge = old_price_low - surcharge
   ```

3. **Verify surcharge value:**
   - Check your energy contract
   - Default Netherlands: 0.11 €/kWh
   - Adjust if your surcharge is different

### Issue 3: Missing Energy Price Data

**Symptom:** Strategy logs "Could not read SOC or price" or adaptive features don't work.

**Cause:**
- Price sensor doesn't have `energy_prices` attribute
- Price data is incomplete or outdated

**Fix:**
1. **Check price sensor attributes:**
   - In Developer Tools > States, check your price sensor
   - Look for `energy_prices` attribute with 24 hourly values

2. **Verify integration:**
   - Check your energy price integration (ha-dsmr, Nordic Energy, etc.)
   - Restart Home Assistant to refresh data
   - Check integration logs for errors

3. **Test with manual price sensor:**
   ```yaml
   # Create a test price sensor with hardcoded values
   sensor:
     - platform: template
       sensors:
         test_energy_price:
           friendly_name: "Test Energy Price"
           value_template: "{{ state_attr('sensor.time', 'hour') | int * 0.01 }}"
           attribute_templates:
             energy_prices: >
               {% set prices = {} %}
               {% for hour in range(24) %}
                 {% set price = hour * 0.01 %}
                 {% set ts = now().strftime('%Y-%m-%d') + 'T' + '%02d' % hour + ':00:00' %}
                 {% do prices.update({ts: price}) %}
               {% endfor %}
               {{ prices | tojson }}
   ```

### Issue 4: Unexpected Season Behavior

**Symptom:** Strategy uses winter timing when you expect summer, or vice versa.

**Cause:**
- Season mode set incorrectly
- Auto detection not working as expected
- Daylight hours don't match your location

**Fix:**
1. **Check current season:**
   - Look at `sensor.sessy_strategy_status` state
   - Check `season_mode_source` attribute

2. **Adjust season configuration:**
   ```yaml
   # Option A: Force explicit season
   season_mode: summer  # or winter
   
   # Option B: Adjust auto detection
   season_mode: auto
   season_day_start: 7   # Earlier for your location
   season_day_end: 19     # Later for your location
   season_auto_fallback: summer  # Change fallback if needed
   ```

3. **Check price data for auto detection:**
   - Auto detection uses `daily_min_price_hour` from `energy_prices`
   - Verify this value is what you expect
   - If `daily_min_price_hour` is between `season_day_start` and `season_day_end`, it's summer

### Issue 5: Performance Issues

**Symptom:** AppDaemon is slow, strategy takes too long to respond.

**Cause:**
- Too many live entities causing frequent re-runs
- Slow Home Assistant/AppDaemon system
- Network latency

**Fix:**
1. **Increase debounce delay:**
   ```yaml
   rerun_debounce_s: 3.0  # Slower response, less frequent re-runs
   ```

2. **Reduce live entities:**
   - Only enable live tuning for parameters you actively adjust
   - Remove entities for parameters you don't change often

3. **Optimize system:**
   - Restart Home Assistant and AppDaemon
   - Check system resources (CPU, memory)
   - Consider running on faster hardware

---

## Rollback Procedure

If you encounter issues that you cannot resolve, you can roll back to your previous version.

**What to do:** Restore your previous configuration and files.

**How to do it:**

1. **Stop AppDaemon:**
   ```bash
   appdaemon stop
   ```

2. **Restore files:**
   ```bash
   # Restore apps.yaml
   cp /config/appdaemon/apps/apps.yaml.backup /config/appdaemon/apps/apps.yaml
   
   # Restore strategy file
   cp /config/appdaemon/apps/sessy_strategy.py.backup /config/appdaemon/apps/sessy_strategy.py
   ```

3. **Restore entity configurations (if needed):**
   ```bash
   cp /config/configuration.yaml.backup /config/configuration.yaml
   ```

4. **Restart Home Assistant and AppDaemon:**
   ```bash
   hassio ha restart
   appdaemon start
   ```

5. **Verify rollback:**
   - Check that your old configuration is active
   - Verify the strategy is working as it did before

---

## Best Practices for Migration

- [x] **Do:** Backup everything before starting
- [x] **Do:** Test during low-usage periods first
- [x] **Do:** Validate configuration with YAML linter
- [x] **Do:** Start with default values and adjust gradually
- [x] **Do:** Monitor closely for the first few days
- [x] **Do:** Keep old configuration until new version is validated
- ❌ **Don't:** Migrate during critical energy periods (peak hours)
- ❌ **Don't:** Delete old files until new version is working
- ❌ **Don't:** Change multiple parameters at once
- ❌ **Don't:** Assume old behavior will be identical

---

## See Also

- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [Entity Reference](../reference/entity-reference.md)
- [How to Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)
- [How to Tune Price Thresholds](../how-to/tune-price-thresholds.md)
- [How to Debug Strategy Decisions](../how-to/debug-strategy-decisions.md)

---

## Migration Checklist

### Before Migration
- [ ] Backed up current apps.yaml
- [ ] Backed up current sessy_strategy.py
- [ ] Backed up Home Assistant configuration
- [ ] Documented current thresholds and behavior
- [ ] Identified current version
- [ ] Reviewed breaking changes for your version

### During Migration
- [ ] Updated parameter names in apps.yaml
- [ ] Converted price thresholds (raw vs import)
- [ ] Added new required parameters
- [ ] Updated entity references
- [ ] Created new required entities
- [ ] Added live tuning entities (optional)
- [ ] Validated YAML syntax

### After Migration
- [ ] Restarted AppDaemon
- [ ] Verified strategy starts and runs
- [ ] Checked status sensor is created and updated
- [ ] Tested each priority branch
- [ ] Tested mode switching
- [ ] Tested live tuning (if configured)
- [ ] Monitored for 24-48 hours
- [ ] Adjusted configuration as needed

### Rollback Preparedness
- [ ] Know rollback procedure
- [ ] Have backups ready
- [ ] Can quickly restore previous version

---

## Getting Help with Migration

If you encounter issues during migration:

1. **Check this guide** for common issues and solutions
2. **Review the status sensor** for current values and conditions
3. **Check AppDaemon logs** for error messages
4. **Verify entity availability** in Home Assistant
5. **Consult the debugging guide** for step-by-step diagnosis
6. **Check the repository issues** for known problems and solutions
7. **Ask in the community** with specific details about:
   - Your old version
   - Your new configuration
   - The specific issue you're encountering
   - Relevant log entries

---

*Last updated: 2026-08-01*