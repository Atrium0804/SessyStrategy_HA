---
title: Debug Strategy Decisions
doc_type: how-to
problem: "Why didn't it charge/discharge when I expected?"
solution: "Systematically diagnose strategy decisions using status sensor, logs, and priority chain analysis"
audience: users
tags:
  - debugging
  - troubleshooting
  - diagnostics
  - strategy
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Debug Strategy Decisions

**Problem:** Your SessyStrategy isn't behaving as expected — it's not charging when prices are cheap, not discharging when prices are high, or making decisions that don't seem optimal.

**Solution:** Use a systematic debugging approach to identify exactly why the strategy made (or didn't make) a particular decision. This guide covers checking the status sensor, reading logs, understanding the priority chain, and fixing common issues.

---

## 📚 Related Documentation

- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [Status Sensor Attributes Reference](../reference/status-sensor-attributes.md)
- [Price Basis: Raw vs Import Explained](../explanation/price-basis-raw-vs-import.md)
- [How to Tune Price Thresholds](../how-to/tune-price-thresholds.md)
- [How to Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)

---

## 🎯 Understanding Strategy Decision Making

### The Priority Chain Evaluation

SessyStrategy evaluates conditions in strict priority order. **The first matching condition wins** — lower priorities are never evaluated if a higher one matches.

```
┌─────────────────────────────────────────────────────────────┐
│                    STRATEGY PRIORITY CHAIN                      │
├─────────────────────────────────────────────────────────────┤
│  Priority 1: Price-Spike Discharge                              │
│  ├─ Condition: price > price_discharge                          │
│  └─ Action: Battery setpoint, discharge toward soc_floor        │
├─────────────────────────────────────────────────────────────┤
│  Priority 2: Cheap/Negative Price Charge                        │
│  ├─ Condition: price < price_charge AND soc < cheap_soc_target │
│  └─ Action: Battery setpoint, charge toward ceiling             │
├─────────────────────────────────────────────────────────────┤
│  Priority 3: Pre-Peak Charge Window                            │
│  ├─ Condition: prepeak_start <= hour < prepeak_end             │
│  ├─ Condition: soc < soc_target                                │
│  └─ Condition: (expected_peak - price) >= min_arbitrage_margin  │
│  └─ Action: Battery setpoint, charge toward soc_target          │
├─────────────────────────────────────────────────────────────┤
│  Priority 4: Evening Peak Excess Discharge                      │
│  ├─ Condition: evening_peak_start <= hour < evening_peak_end   │
│  ├─ Condition: soc > soc_target                                │
│  └─ Action: Grid setpoint, export excess                       │
├─────────────────────────────────────────────────────────────┤
│  Priority 5: Default                                           │
│  ├─ Condition: Always (fallthrough)                            │
│  └─ Action: Grid setpoint 0W (absorb solar, block export)     │
└─────────────────────────────────────────────────────────────┘
```

### Mode Dispatch (Before Priority Chain)

Before evaluating the priority chain, the strategy checks the operating mode:

```
mode_select → [optimized | grid_setpoint | battery_setpoint | sessy_dynamic | eco | idle]
```

- **Only `optimized` mode** runs the priority chain
- Other modes bypass the chain and use direct setpoints or stand-down behavior

---

## ✅ Step-by-Step Debugging Process

### Step 1: Quick Check — Status Sensor

The `sensor.sessy_strategy_status` entity is your primary debugging tool. It contains all the information needed to understand any decision.

**What to do:** Check the status sensor in Home Assistant.

**How to do it:**

1. **Find the entity:** `sensor.sessy_strategy_status` (or your configured `status_sensor`)
2. **Check the state:** Shows the `active_branch` (which priority matched)
3. **Check the attributes:** Shows all current values and conditions

**Key attributes to examine:**

```yaml
# State
state: "summer"  # Current active season

# Attributes
active_branch: "default"        # Which priority matched
season_mode_source: "auto"    # Source of season mode
soc: 65.3                    # Current SOC percentage
raw_price: 0.25000           # Current raw (export) price
import_price: 0.36000        # raw_price + surcharge
price_discharge: 0.39        # Current discharge threshold
price_charge: -0.10          # Current charge threshold
soc_target: 70               # Current SOC target
soc_floor: 0                # Current SOC floor
cheap_soc_target: 100        # Current cheap charge ceiling
min_arbitrage_margin: 0.05   # Current arbitrage margin
prepeak_start: 15           # Current pre-peak window start
prepeak_end: 17             # Current pre-peak window end
prepeak_window_h: 2.0       # Current pre-peak charge window
daily_min_price_hour: 3      # Hour of day's minimum price
daily_min_price: 0.15000     # Value of day's minimum price
```

**Expected result:** You now have a snapshot of all conditions at the time of the last strategy run.

### Step 2: Identify the Active Branch

The `active_branch` attribute tells you exactly which decision path was taken:

| Branch | Priority | Meaning |
|--------|----------|---------|
| `discharge` | 1 | Price-spike discharge active |
| `cheap_charge` | 2 | Cheap price charging active |
| `cheap_charge_full` | 2 | Cheap price but SOC already at ceiling |
| `prepeak_charge` | 3 | Pre-peak charging active |
| `prepeak_full` | 3 | In pre-peak window but SOC already at target |
| `prepeak_skip` | 3 | In pre-peak window but arbitrage margin too small |
| `evening_peak_excess` | 4 | Evening peak excess discharge active |
| `default` | 5 | Default grid setpoint 0W |
| `manual_grid` | - | Manual grid setpoint mode |
| `manual_battery` | - | Manual battery setpoint mode |
| `idle` | - | Idle mode |
| `sessy_dynamic` | - | Sessy dynamic mode |
| `eco` | - | Eco mode |

**Debugging tip:** If `active_branch` is not what you expected, note the current conditions and proceed to Step 3.

### Step 3: Verify Mode and Season

**Check operating mode:**
- If `active_branch` is `manual_grid`, `manual_battery`, `idle`, `sessy_dynamic`, or `eco`, the priority chain was **bypassed**
- Check your `mode_select` entity — it might not be set to `optimized`

**Check season mode:**
- `state` shows the current active season (`auto`, `summer`, `winter`)
- `season_mode_source` shows where this came from
- Winter-specific overrides might be affecting your thresholds

**Debugging questions:**
- Is the mode set to `optimized`?
- Is the season what you expect?
- If using `auto` season, is `daily_min_price_hour` within the daytime range?

### Step 4: Analyze Priority Chain Conditions

Work through the priority chain manually using the status sensor values:

#### Priority 1: Price-Spike Discharge
```
Condition: raw_price > price_discharge
Your values: raw_price = 0.25000, price_discharge = 0.39
Evaluation: 0.25000 > 0.39? NO → Priority 1 not triggered
```

If this condition is **NOT met**, check Priority 2.

#### Priority 2: Cheap/Negative Price Charge
```
Condition 1: price < price_charge
Condition 2: soc < cheap_soc_target
Your values: price = 0.25000, price_charge = -0.10, soc = 65.3, cheap_soc_target = 100
Evaluation: (0.25000 < -0.10)? NO → Priority 2 not triggered
Evaluation: (0.25000 < -0.10) AND (65.3 < 100)? NO → Priority 2 not triggered
```

If this condition is **NOT met**, check Priority 3.

#### Priority 3: Pre-Peak Charge Window
```
Condition 1: prepeak_start <= current_hour < prepeak_end
Condition 2: soc < soc_target
Condition 3: (expected_peak - price) >= min_arbitrage_margin
Your values: prepeak_start = 15, prepeak_end = 17, hour = 14, soc = 65.3, soc_target = 70
Evaluation: (15 <= 14 < 17)? NO → Priority 3 not triggered
```

If this condition is **NOT met**, check Priority 4.

**Note:** To see `expected_peak`, you may need to check logs or add debug logging. The strategy calculates this as the maximum remaining raw price for the day.

#### Priority 4: Evening Peak Excess Discharge
```
Condition 1: evening_peak_start <= current_hour < evening_peak_end
Condition 2: soc > soc_target
Your values: evening_peak_start = 18, evening_peak_end = 23, hour = 14, soc = 65.3, soc_target = 70
Evaluation: (18 <= 14 < 23)? NO → Priority 4 not triggered
Evaluation: (18 <= 14 < 23) AND (65.3 > 70)? NO → Priority 4 not triggered
```

If this condition is **NOT met**, Priority 5 (default) is used.

#### Priority 5: Default
```
Condition: Always (no conditions to check)
Action: Grid setpoint 0W — absorb solar, block export
```

### Step 5: Read the AppDaemon Logs

The logs provide detailed information about each strategy decision.

**What to do:** Check AppDaemon logs for strategy decisions.

**How to do it:**

1. **Access logs:**
   - Check AppDaemon's log file (typically `appdaemon.log` in your config directory)
   - Or use the AppDaemon web UI: http://your-appdaemon:5050/logs
   - Or use the command line: `tail -f /path/to/appdaemon.log`

2. **Look for strategy log entries:**
   ```
   # Format: Hour=XX  SOC=XX%  Raw price=X.XXXXX  Import price=X.XXXXX
   Hour=14  SOC=65%  Raw price=0.25000  Import price=0.36000
   DEFAULT: grid setpoint 0W — absorb solar, block export
   
   # Priority 1 example:
   Hour=19  SOC=85%  Raw price=0.45000  Import price=0.56000
   DISCHARGE override: import price 0.560 > 0.50 — battery setpoint 1800W (SOC 85% → floor 0% over 2.50h)
   
   # Priority 2 example:
   Hour=03  SOC=45%  Raw price=-0.15000  Import price=-0.04000
   CHEAP CHARGE: raw price -0.15000 < -0.10 — battery setpoint -2200W (SOC 45% → 100% over 2.00h cheap window)
   
   # Priority 3 example:
   Hour=16  SOC=65%  Raw price=0.25000  Import price=0.36000
   PRE-PEAK CHARGE: battery setpoint -2000W (SOC 65% → target 70% over 2.0h)
   
   # Priority 3 skip example:
   Hour=16  SOC=65%  Raw price=0.32000  Import price=0.43000
   PRE-PEAK SKIP: best remaining price 0.350 vs current 0.320 (spread < margin 0.05) — holding grid setpoint 0W
   
   # Priority 4 example:
   Hour=20  SOC=85%  Raw price=0.40000  Import price=0.51000
   EVENING PEAK EXCESS: SOC 85% > target 70% — grid export setpoint -800W (spread over 2.50h remaining peak window)
   ```

3. **Enable debug logging (if needed):**
   The strategy already logs key decisions. For more detail, you can:
   - Check the `_publish_status()` calls in the source code
   - Add custom debug logging to AppDaemon configuration

### Step 6: Check External Dependencies

#### Entity Availability
The strategy requires these entities to function:

| Entity | Purpose | Check |
|--------|---------|-------|
| `soc_sensor` | Current battery SOC | Must exist and return numeric value |
| `price_sensor` | Current energy price | Must exist and return numeric value |
| `strategy_select` | Sessy strategy selector | Must exist for setpoint modes |
| `grid_target` | Grid power target | Required for grid setpoint mode |
| `battery_setpoint` | Battery power setpoint | Required for battery setpoint mode |

**How to check:**
1. Verify all required entities exist in Home Assistant
2. Check their states are numeric (not "unknown", "unavailable", or non-numeric)
3. For price_sensor, check it has the `energy_prices` attribute with 24 hourly prices

#### Price Sensor Data
The strategy needs both:
- **Current price**: From sensor state or `energy_prices` attribute
- **Daily prices**: From `energy_prices` attribute for spread window and pre-peak calculations

**Check `energy_prices` attribute:**
```yaml
# In Developer Tools > States, check your price sensor
entity_id: sensor.sessy_dnhh_energy_price
state: 0.25
attributes:
  energy_prices:
    "2026-08-01T00:00:00": 0.15
    "2026-08-01T01:00:00": 0.12
    "2026-08-01T02:00:00": 0.08
    # ... all 24 hours
```

If `energy_prices` is missing or incomplete:
- Check your energy price integration (ha-dsmr, Nordic Energy, etc.)
- Verify the integration is properly configured
- Restart Home Assistant to refresh the data

---

## 🔍 Common Issues and Fixes

### Issue 1: "It's not charging during cheap hours"

**Symptoms:**
- Strategy stays in `default` mode when you expect `cheap_charge`
- Battery doesn't charge during negative or very low prices

**Checklist:**
- [ ] Is `price_charge` set correctly?
  - Current: `price_charge: -0.10`
  - Needed: Should be higher (less negative) than current cheap prices
  - Fix: Raise `price_charge` to `-0.05` or `0.00`

- [ ] Is current `raw_price` < `price_charge`?
  - Current: `raw_price = 0.05, price_charge = -0.10`
  - Evaluation: `0.05 < -0.10`? NO
  - Fix: Lower `price_charge` or wait for cheaper prices

- [ ] Is SOC below `cheap_soc_target`?
  - Current: `soc = 100, cheap_soc_target = 100`
  - Evaluation: `100 < 100`? NO
  - Fix: Lower `cheap_soc_target` to `95` or wait for SOC to drop

- [ ] Are price entities available?
  - Check: `soc_sensor` and `price_sensor` exist and have valid states
  - Fix: Verify entities and their configuration

**Example fix:**
```yaml
# In apps.yaml
price_charge: -0.05  # Charge when raw < -€0.05
cheap_soc_target: 95  # Stop charging at 95%
```

### Issue 2: "It's not discharging during peak prices"

**Symptoms:**
- Strategy stays in `default` mode when you expect `discharge`
- Battery doesn't discharge during high prices

**Checklist:**
- [ ] Is `price_discharge` set correctly?
  - Current: `price_discharge: 0.39`
  - Needed: Should be lower than current peak prices
  - Fix: Lower `price_discharge` to `0.35`

- [ ] Is current `raw_price` > `price_discharge`?
  - Current: `raw_price = 0.35, price_discharge = 0.39`
  - Evaluation: `0.35 > 0.39`? NO
  - Fix: Lower `price_discharge` or wait for higher prices

- [ ] Is SOC above `soc_floor`?
  - Current: `soc = 0, soc_floor = 0`
  - Evaluation: `0 > 0`? NO
  - Fix: Raise `soc_floor` to `5` or wait for SOC to increase

- [ ] Is battery in manual mode?
  - Check: `mode_select` should be `optimized`
  - Fix: Switch mode selector back to `optimized`

**Example fix:**
```yaml
# In apps.yaml
price_discharge: 0.35  # Discharge when raw > €0.35
soc_floor: 5  # Keep at least 5% charge
```

### Issue 3: "It's not charging in pre-peak window"

**Symptoms:**
- Strategy shows `default` or `prepeak_skip` instead of `prepeak_charge`
- Battery doesn't charge before evening peak

**Checklist:**
- [ ] Is current hour within pre-peak window?
  - Current: `hour = 14, prepeak_start = 15, prepeak_end = 17`
  - Evaluation: `15 <= 14 < 17`? NO
  - Fix: Adjust `prepeak_start` to `14`

- [ ] Is SOC below target?
  - Current: `soc = 75, soc_target = 70`
  - Evaluation: `75 < 70`? NO
  - Fix: Lower `soc_target` to `75` or wait for SOC to drop

- [ ] Is arbitrage margin sufficient?
  - Current: `expected_peak = 0.35, price = 0.32, min_arbitrage_margin = 0.05`
  - Calculation: `0.35 - 0.32 = 0.03`
  - Evaluation: `0.03 >= 0.05`? NO
  - Fix: Lower `min_arbitrage_margin` to `0.02` or wait for better spread

- [ ] Are price forecasts available?
  - Check: `energy_prices` attribute exists and has future prices
  - Fix: Verify price sensor integration

**Example fix:**
```yaml
# In apps.yaml
prepeak_start: 14  # Start pre-peak at 14:00
min_arbitrage_margin: 0.02  # Lower margin requirement
```

### Issue 4: "It's charging/discharging too aggressively"

**Symptoms:**
- Battery cycles too frequently
- High power setpoints causing inverter stress
- Excessive wear on battery

**Checklist:**
- [ ] Are thresholds too close?
  - Current: `price_discharge = 0.39, price_charge = -0.10`
  - Issue: Large gap between thresholds can cause frequent switching
  - Fix: Consider your actual price ranges

- [ ] Is min_window_h too short?
  - Current: `min_window_h = 0.5`
  - Issue: Short window causes high power spikes
  - Fix: Increase to `min_window_h = 2.0` or higher

- [ ] Are SOC targets appropriate?
  - Current: `soc_target = 95, soc_floor = 5`
  - Issue: Narrow SOC range causes frequent charging/discharging
  - Fix: Widen range: `soc_target = 80, soc_floor = 20`

**Example fix:**
```yaml
# In apps.yaml
min_window_h: 3.0  # Spread over at least 3 hours
soc_target: 70     # Target 70% instead of higher
soc_floor: 10      # Keep minimum 10%
```

### Issue 5: "Strategy shows wrong season"

**Symptoms:**
- Wrong timing windows (winter vs summer)
- Status sensor shows unexpected season

**Checklist:**
- [ ] Is season_mode set correctly?
  - Current: `season_mode: auto`
  - Check: `season_mode_source` in status sensor

- [ ] Is auto detection working?
  - Check: `daily_min_price_hour` in status sensor
  - Check: `season_day_start = 8, season_day_end = 18`
  - Evaluation: If `daily_min_price_hour` is between 8-18, it's summer; otherwise winter
  - Fix: Adjust `season_day_start` and `season_day_end` or set explicit season

- [ ] Is live season entity overriding?
  - Check: `season_mode_entity` configuration
  - Check: Live entity value
  - Fix: Remove entity or adjust its value

**Example fix:**
```yaml
# Option A: Explicit season
season_mode: winter  # Force winter mode

# Option B: Adjust auto detection hours
season_day_start: 7   # Earlier daylight start
season_day_end: 19    # Later daylight end

# Option C: Remove live entity override
season_mode_entity:   # Remove this line to disable live override
```

### Issue 6: "Strategy not running at all"

**Symptoms:**
- No log entries from strategy
- Status sensor not updating
- Battery not responding to any conditions

**Checklist:**
- [ ] Is AppDaemon running?
  - Check: `appdaemon status` or web UI
  - Fix: Start AppDaemon if stopped

- [ ] Is strategy configured in apps.yaml?
  - Check: `sessy_strategy` section exists
  - Fix: Verify configuration file

- [ ] Are required entities available?
  - Check: `soc_sensor` and `price_sensor` exist
  - Fix: Create missing entities or fix their configuration

- [ ] Did AppDaemon restart recently?
  - Check: Wait 30+ seconds for initial delay
  - Fix: Wait for first run (strategy delays 30 seconds on startup)

**Example fix:**
```bash
# Restart AppDaemon
appdaemon restart

# Check logs after restart
appdaemon logs
```

---

## 🎯 Advanced Debugging Techniques

### Technique 1: Manual Priority Chain Simulation

Use the status sensor values to manually simulate what the strategy should do:

```
# Get values from status sensor
soc = 65.0
raw_price = 0.28
import_price = 0.39  # raw_price + surcharge
price_discharge = 0.39
price_charge = -0.10
soc_target = 70
soc_floor = 0
cheap_soc_target = 100
current_hour = 14
prepeak_start = 15
prepeak_end = 17
evening_peak_start = 18
evening_peak_end = 23

# Simulate priority chain
print("=== PRIORITY CHAIN SIMULATION ===")

# Priority 1
if raw_price > price_discharge:
    print("P1: DISCHARGE - raw_price", raw_price, "> price_discharge", price_discharge)
    exit()
else:
    print("P1: NOT MATCHED - raw_price", raw_price, "<= price_discharge", price_discharge)

# Priority 2
if raw_price < price_charge and soc < cheap_soc_target:
    print("P2: CHEAP CHARGE - raw_price", raw_price, "< price_charge", price_charge, "AND soc", soc, "< cheap_soc_target", cheap_soc_target)
    exit()
elif raw_price < price_charge:
    print("P2: CHEAP CHARGE FULL - raw_price", raw_price, "< price_charge", price_charge, "BUT soc", soc, ">= cheap_soc_target", cheap_soc_target)
    exit()
else:
    print("P2: NOT MATCHED")

# Priority 3
if prepeak_start <= current_hour < prepeak_end:
    if soc >= soc_target:
        print("P3: PRE-PEAK FULL - soc", soc, ">= soc_target", soc_target)
        exit()
    else:
        # Need expected_peak from logs or status
        expected_peak = 0.45  # Example value
        min_arbitrage_margin = 0.05
        if (expected_peak - raw_price) >= min_arbitrage_margin:
            print("P3: PRE-PEAK CHARGE - soc", soc, "< soc_target", soc_target, "AND spread", expected_peak - raw_price, ">= margin", min_arbitrage_margin)
            exit()
        else:
            print("P3: PRE-PEAK SKIP - spread", expected_peak - raw_price, "< margin", min_arbitrage_margin)
            exit()
else:
    print("P3: NOT IN WINDOW - hour", current_hour, "not in", prepeak_start, "-", prepeak_end)

# Priority 4
if evening_peak_start <= current_hour < evening_peak_end:
    if soc > soc_target:
        print("P4: EVENING PEAK EXCESS - soc", soc, "> soc_target", soc_target)
        exit()
    else:
        print("P4: NOT MATCHED - soc", soc, "<= soc_target", soc_target)
else:
    print("P4: NOT IN WINDOW - hour", current_hour, "not in", evening_peak_start, "-", evening_peak_end)

# Priority 5
print("P5: DEFAULT - grid setpoint 0W")
```

**Expected output:**
```
=== PRIORITY CHAIN SIMULATION ===
P1: NOT MATCHED - raw_price 0.28 <= price_discharge 0.39
P2: NOT MATCHED
P3: NOT IN WINDOW - hour 14 not in 15 - 17
P4: NOT IN WINDOW - hour 14 not in 18 - 23
P5: DEFAULT - grid setpoint 0W
```

This matches the actual strategy behavior in the logs.

### Technique 2: Enhanced Logging Script

Create a custom script to log additional debugging information:

```python
# Add to your apps.yaml or create a separate debug app
def log_debug_info(self):
    """Log extended debugging information."""
    soc = self._get_soc()
    price = self._get_current_price()
    import_price = price + self.surcharge if price else None
    
    self.log(
        f"DEBUG: Hour={self.datetime().hour:02d}  "
        f"SOC={soc:.1f}%  "
        f"Raw={price:.5f}  "
        f"Import={import_price:.5f if import_price else 'N/A'}  "
        f"Mode={self._active_mode()}  "
        f"Season={self._active_season_mode()}"
    )
    
    # Log all threshold values
    self.log(
        f"DEBUG: Thresholds - "
        f"discharge={self._tunable(self.price_discharge, self.price_discharge_entity):.5f}  "
        f"charge={self._tunable(self.price_charge, self.price_charge_entity):.5f}  "
        f"soc_target={self._tunable(self.soc_target, self.soc_target_entity):.1f}  "
        f"soc_floor={self._tunable(self.soc_floor, self.soc_floor_entity):.1f}"
    )
```

### Technique 3: Price Data Validation

Check if your price sensor has complete data for the day:

```python
# Python script to validate price data
prices = self._get_prices_dict()
if prices:
    today = self.datetime().strftime("%Y-%m-%d")
    hourly_prices = []
    for hour in range(24):
        key = f"{today}T{hour:02d}:00:00"
        if key in prices:
            hourly_prices.append(float(prices[key]))
        else:
            hourly_prices.append(None)
    
    self.log(f"DEBUG: Hourly prices for {today}: {hourly_prices}")
    
    # Check for missing data
    missing = [i for i, p in enumerate(hourly_prices) if p is None]
    if missing:
        self.log(f"DEBUG: Missing price data for hours: {missing}")
```

---

## 📝 Best Practices

- ✅ **Do:** Start with the status sensor — it has most of the information you need
- ✅ **Do:** Check logs for the exact conditions that were evaluated
- ✅ **Do:** Work through the priority chain systematically
- ✅ **Do:** Verify all required entities exist and have valid data
- ✅ **Do:** Check price sensor has complete `energy_prices` data
- ✅ **Do:** Test one change at a time to isolate issues
- ✅ **Do:** Monitor for at least one full day after making changes
- ❌ **Don't:** Assume the strategy should be doing something without checking the conditions
- ❌ **Don't:** Change multiple parameters simultaneously — it makes debugging harder
- ❌ **Don't:** Forget to check if you're in manual mode or a different season
- ❌ **Don't:** Expect the strategy to predict future prices beyond what's in `energy_prices`

---

## 🔗 See Also

- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [Status Sensor Attributes Reference](../reference/status-sensor-attributes.md)
- [How to Tune Price Thresholds](../how-to/tune-price-thresholds.md)
- [How to Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)
- [How to Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)

---

## 📊 Quick Checklist

- [ ] Checked status sensor state and attributes
- [ ] Identified the active_branch from status sensor
- [ ] Verified operating mode is `optimized`
- [ ] Verified current season and thresholds
- [ ] Worked through priority chain conditions manually
- [ ] Checked AppDaemon logs for strategy decisions
- [ ] Verified all required entities exist and have valid data
- [ ] Checked price sensor has complete energy_prices attribute
- [ ] Simulated priority chain with actual values
- [ ] Made and tested one configuration change at a time

---

## 🚨 Emergency Debugging Script

If you're completely stuck, run this emergency debugging sequence:

1. **Check AppDaemon is running:**
   ```bash
   appdaemon status
   ```

2. **Check strategy is loaded:**
   ```bash
   appdaemon list
   # Should show sessy_strategy as loaded
   ```

3. **Force immediate strategy run:**
   - Change any live input entity (e.g., adjust a price threshold by €0.01)
   - Or wait for next 5-minute cycle

4. **Check status sensor:**
   - Look at `sensor.sessy_strategy_status` in Home Assistant
   - Note the `active_branch`

5. **Check required entities:**
   ```bash
   # In Home Assistant Developer Tools > States
   sensor.sessy_battery_alt9_state_of_charge
   sensor.sessy_dnhh_energy_price
   ```

6. **Check mode:**
   - Verify `select.home_battery_mode` (or your mode entity) is set to `optimized`

7. **Review last 10 log entries:**
   ```bash
   tail -n 50 /path/to/appdaemon.log | grep -i sessy
   ```

---

*Last updated: 2026-08-01*