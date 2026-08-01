# Algorithms

*Last updated: 2026-08-01 | Part of [Reference Documentation](../)*

---

## Overview

SessyStrategy uses several key algorithms for calculating charge/discharge power, determining time windows, and making price-based decisions. All algorithms are designed to be **lean, deterministic, and self-correcting** — avoiding complex optimization in favor of simple, robust heuristics.

---

## Setpoint Calculation Algorithms

### 1. Charge Setpoint (Pre-Peak)

**Method:** `_charge_setpoint(soc: float, soc_target: float, prepeak_window_h: float) -> float`

**Purpose:** Calculate power to charge the battery during the pre-peak window (Priority 3).

**Formula:**
```
gap_wh = (soc_target - soc) / 100.0 * capacity_wh
spread_w = gap_wh / prepeak_window_h
power_w = spread_w * 1.5  # Charge 50% faster than even spread
power_w = min(power_w, max_power_w)  # Cap at hardware limit
min_power_w = max_power_w * 0.66  # Minimum power threshold
result = max(min_power_w, power_w)
```

**Rationale:**
- Spreads the required energy over the pre-peak window
- Charges 50% faster than the even spread to finish early
- Capped at `max_power_w` to avoid exceeding hardware limits
- Minimum power threshold (66% of max) prevents wasting surplus PV energy when SOC is near target

**Example:**
- `capacity_wh = 5000` (5 kWh battery)
- `soc = 40%`, `soc_target = 70%`, `prepeak_window_h = 2.0`
- `max_power_w = 2200`

```
gap_wh = (70 - 40) / 100 * 5000 = 1500 Wh
gap_wh = 1500 Wh = 1.5 kWh needed
spread_w = 1500 / 2.0 = 750 W even spread
power_w = 750 * 1.5 = 1125 W (50% faster)
min_power_w = 2200 * 0.66 = 1452 W
result = max(1452, 1125) = 1452 W
```

**Edge cases:**
- If `soc >= soc_target`: Returns value from caller's condition check (not called)
- If `power_w < min_power_w`: Uses `min_power_w` instead
- If `power_w > max_power_w`: Uses `max_power_w` instead

---

### 2. Discharge Setpoint (Price Spike)

**Method:** `_discharge_setpoint(soc: float, soc_floor: float, window_h: float) -> float`

**Purpose:** Calculate power to discharge the battery during a price spike (Priority 1).

**Formula:**
```
available_wh = (soc - soc_floor) / 100.0 * capacity_wh
if available_wh <= 0:
    return 0  # Already at floor
spread_w = available_wh / window_h
result = max(50, min(spread_w, max_power_w))
```

**Rationale:**
- Spreads available energy above floor over the window
- Minimum of 50W ensures some discharge even with small gaps
- Capped at `max_power_w`
- Self-correcting: if SOC doesn't reach floor, next cycle continues discharging

**Example:**
- `capacity_wh = 5000`
- `soc = 80%`, `soc_floor = 20%`, `window_h = 2.0` (adaptive)

```
available_wh = (80 - 20) / 100 * 5000 = 3000 Wh = 3 kWh
spread_w = 3000 / 2.0 = 1500 W
result = max(50, min(1500, 2200)) = 1500 W
```

**Edge cases:**
- If `soc <= soc_floor`: Returns 0 (already at floor)
- If `spread_w < 50`: Returns 50 (minimum discharge power)
- If `spread_w > max_power_w`: Returns `max_power_w`

---

### 3. Cheap Charge Setpoint

**Method:** `_cheap_charge_setpoint(soc: float, cheap_soc_target: float, window_h: float) -> float`

**Purpose:** Calculate power to charge during cheap/negative price hours (Priority 2).

**Formula:**
```
if soc >= cheap_soc_target:
    return 0  # Already at ceiling
return max_power_w  # Always charge at maximum power
```

**Rationale:**
- Simple: when prices are cheap enough to charge, go all-in
- Charges at maximum power to capture the cheap energy as quickly as possible
- Window is used for adaptive timing, not power calculation
- Self-correcting: stops when SOC reaches ceiling

**Example:**
- `max_power_w = 2200`
- `soc = 60%`, `cheap_soc_target = 100%`
- Result: `-2200 W` (2200W charge)

**Note:** Negative sign indicates charge direction is handled by the caller (`_set_battery_setpoint(-charge_w)`).

---

### 4. Evening Peak Excess Discharge Setpoint

**Method:** `_evening_peak_excess_setpoint(soc: float, soc_target: float, hours_remaining: float) -> float`

**Purpose:** Calculate power to discharge excess SOC during evening peak (Priority 4).

**Formula:**
```
gap_wh = (soc - soc_target) / 100.0 * capacity_wh
spread_w = gap_wh / max(hours_remaining, 0.083)  # avoid div/0
result = max(50, min(spread_w, max_power_w))
```

**Rationale:**
- Spreads excess energy above target over remaining peak hours
- Applied as negative grid setpoint (export), so battery covers household load AND export
- Minimum 50W ensures some discharge
- 0.083 hour minimum (5 minutes) prevents division by zero for very short windows

**Example:**
- `capacity_wh = 5000`
- `soc = 90%`, `soc_target = 70%`, `hours_remaining = 1.5`

```
gap_wh = (90 - 70) / 100 * 5000 = 1000 Wh = 1 kWh
hours_remaining = 1.5
spread_w = 1000 / 1.5 = 666.67 W
result = max(50, min(666.67, 2200)) = 666.67 W ≈ 667 W
```

**Grid setpoint:** `-667 W` (export 667W)

---

## Adaptive Spread Window Algorithm

### Contiguous Price Hours

**Method:** `_contiguous_price_hours(threshold: float, above: bool) -> int`

**Purpose:** Count consecutive upcoming hours where price stays past threshold.

**Algorithm:**
```
1. Get prices dict from price_sensor.energy_prices
2. If no prices: return 1 (minimum)
3. Start at current hour, rounded down to hour boundary
4. For up to 48 hours forward:
   a. If hour key not in prices: break
   b. Get price for that hour
   c. If above=True: check if price > threshold
      If below=True: check if price < threshold
   d. If condition met: count++
   e. Else: break
5. Return max(count, 1)  # Always at least 1
```

**Purpose:** Determines how long the favorable price condition will last.

**Example:**
- Current hour: 14:00
- Threshold: 0.39, above=True
- Prices: 14=0.45, 15=0.50, 16=0.48, 17=0.35, 18=0.40
- Contiguous hours > 0.39: 14, 15, 16 (3 hours)
- Result: 3

---

### Spread Window Hours

**Method:** `_spread_window_h(threshold: float, above: bool) -> float`

**Purpose:** Calculate adaptive window with minimum floor.

**Formula:**
```
run_h = _contiguous_price_hours(threshold, above)
result = max(run_h, min_window_h)
```

**Purpose:** Ensures power is spread over the entire favorable period, but never less than `min_window_h`.

**Rationale:**
- Wider spread = lower power = lower round-trip losses (copper losses scale with current squared)
- Minimum window prevents excessively high power draws
- Adaptive: automatically adjusts to price forecast

**Example:**
- `min_window_h = 2.0`
- `_contiguous_price_hours(0.39, above=True)` returns 3
- Result: `max(3, 2.0) = 3.0` hours

---

## Price Analysis Algorithms

### Maximum Price in Window

**Method:** `_max_price_in_window(start_hour: int, end_hour: int) -> float | None`

**Purpose:** Find the maximum raw price in a given hour range.

**Algorithm:**
```
1. Get prices dict
2. If no prices: return None
3. For hour in range(start_hour, end_hour):
   a. Build key: f"{today}T{hour:02d}:00:00"
   b. If key in prices: parse and add to values list
4. If values not empty: return max(values)
5. Else: return None
```

**Use cases:**
- Pre-peak charge: Check if expected evening peak > current price + margin
- Evening peak excess: Check if any remaining hour exceeds discharge threshold

**Example:**
- `start_hour = 18`, `end_hour = 24`
- Today: 2026-08-01
- Prices: 18=0.25, 19=0.45, 20=0.52, 21=0.48, 22=0.35, 23=0.22
- Result: 0.52

---

### Daily Minimum Price Hour and Value

**Method:** `_daily_min_price_hour_and_value() -> (int | None, float | None)`

**Purpose:** Find the hour and value of today's minimum raw price.

**Algorithm:**
```
1. Get prices dict
2. If no prices: return (None, None)
3. today = current date in YYYY-MM-DD format
4. For hour in 0..23:
   a. key = f"{today}T{hour:02d}:00:00"
   b. If key in prices: parse value
   c. If value < min_price (or min_price is None): update min
5. Return (min_hour, min_price)
```

**Use cases:**
- Season inference: Determine if minimum is during day (summer) or night (winter)
- Status sensor: Publish for visibility

**Example:**
- Today: 2026-08-01
- Prices: 00=0.12, 01=0.08, 02=0.05, ..., 23=0.15
- Result: (2, 0.05)

---

## Season Inference Algorithm

### Infer Season from Price Minimum

**Method:** `_infer_season_from_price_minimum() -> str | None`

**Purpose:** Automatically determine season based on when the cheapest price occurs.

**Logic:**
```
1. Get (min_hour, min_price) from _daily_min_price_hour_and_value()
2. If min_hour is None: return None
3. If season_day_start <= min_hour < season_day_end:
      return "summer"
4. Else:
      return "winter"
```

**Rationale:**
- Summer: Cheapest prices typically during midday (solar surplus)
- Winter: Cheapest prices typically overnight (low demand)
- Daytime definition: `[season_day_start, season_day_end)` (default 8:00-18:00)

**Example:**
- `season_day_start = 8`, `season_day_end = 18`
- `min_hour = 2` (02:00) → winter
- `min_hour = 14` (14:00) → summer
- `min_hour = 8` (08:00) → summer (start is inclusive)
- `min_hour = 18` (18:00) → winter (end is exclusive)

---

### Active Season Mode

**Method:** `_active_season_mode() -> str`

**Purpose:** Resolve the current season mode from all sources.

**Algorithm:**
```
1. Start with configured season_mode from apps.yaml
2. If season_mode_entity is set:
      a. Get entity state
      b. If valid string: override season_mode with entity value
3. If mode is "auto":
      a. Try to infer from _infer_season_from_price_minimum()
      b. If inference succeeds: return inferred season
      c. Else: return season_auto_fallback
4. Else (mode is "summer" or "winter"):
      return mode
```

**Priority:** Entity > Auto-inference > Fallback

---

## Helper Methods

### Tunable Value Resolution

**Method:** `_tunable(default: float, entity_id) -> float`

**Purpose:** Get value from live entity or fall back to default.

**Algorithm:**
```
1. If entity_id is None: return default
2. Try to get entity state
3. Try to parse as float
4. If success: return parsed value
5. Else: return default
```

**Use:** All live-tuning values (SOC targets, prices, margins)

---

### Optional Argument Parsing

**Methods:**
- `_optional_float_arg(key: str) -> float | None`
- `_optional_int_arg(key: str) -> int | None`

**Purpose:** Safely parse optional configuration values.

**Algorithm:**
```
1. Get value from self.args.get(key)
2. If value is None: return None
3. Try to parse as float/int
4. If success: return parsed value
5. Else: return None
```

**Use:** Winter-specific overrides (may be null in config)

---

### Seasonal Value

**Method:** `_seasonal_value(base_value, active_season: str, winter_override) -> float | int`

**Purpose:** Get the appropriate value for the current season.

**Algorithm:**
```
1. If active_season == "winter" and winter_override is not None:
      return winter_override
2. Else:
      return base_value
```

**Use:** SOC floor, pre-peak window parameters

---

### Entity Existence Check

**Method:** `_entity_exists(entity_id: str) -> bool`

**Purpose:** Verify an entity exists and is readable.

**Algorithm:**
```
1. If entity_id is None: return False
2. Try to get entity state
3. If state is not None: return True
4. Else: return False
```

**Use:** All service calls are guarded by this check

---

## Formula Summary Table

| Algorithm | Formula | Purpose | Used In |
|---|---|---|---|
| Charge Setpoint | `(target-soc)/100 * cap / window * 1.5` | Pre-peak charging | Priority 3 |
| Discharge Setpoint | `(soc-floor)/100 * cap / window` | Price spike discharge | Priority 1 |
| Cheap Charge | `max_power_w` (constant) | Cheap price charging | Priority 2 |
| Excess Discharge | `(soc-target)/100 * cap / hours` | Evening surplus export | Priority 4 |
| Adaptive Window | `max(contiguous_hours, min_window)` | Spread window sizing | P1, P2 |
| Max Price | `max(prices[start:end])` | Peak detection | P3, P4 |
| Min Price Hour | `argmin(prices[0:24])` | Season inference | Auto mode |

---

## Example Scenarios

### Scenario 1: Price Spike Discharge

**Conditions:**
- Battery: 5 kWh, 2.2 kW max
- SOC: 80%, Floor: 20%
- Current price: €0.45 raw
- Discharge threshold: €0.39
- Contiguous hours > 0.39: 3 hours
- min_window_h: 2.0

**Calculation:**
```
window_h = max(3, 2.0) = 3.0 hours
available_wh = (80-20)/100 * 5000 = 3000 Wh
spread_w = 3000 / 3.0 = 1000 W
result = max(50, min(1000, 2200)) = 1000 W
```

**Action:** Battery setpoint = 1000W (discharge)

---

### Scenario 2: Pre-Peak Charge

**Conditions:**
- Battery: 5 kWh, 2.2 kW max
- SOC: 40%, Target: 70%
- Current price: €0.15 raw
- Expected peak: €0.50 raw
- Arbitrage margin: €0.05
- Window: 2.0 hours

**Check:**
```
expected_peak - current = 0.50 - 0.15 = 0.35 > 0.05 ✓
```

**Calculation:**
```
gap_wh = (70-40)/100 * 5000 = 1500 Wh
spread_w = 1500 / 2.0 = 750 W
power_w = 750 * 1.5 = 1125 W
min_power_w = 2200 * 0.66 = 1452 W
result = max(1452, 1125) = 1452 W
```

**Action:** Battery setpoint = -1452W (charge)

---

### Scenario 3: Cheap Price Charge

**Conditions:**
- Current price: -€0.15 raw
- Charge threshold: -€0.10
- SOC: 50%, Ceiling: 100%

**Check:**
```
price < threshold: -0.15 < -0.10 ✓
```

**Calculation:**
```
result = max_power_w = 2200 W
```

**Action:** Battery setpoint = -2200W (charge at max)

---

## Edge Cases and Constraints

### Minimum Power Threshold

- **Discharge:** Minimum 50W to ensure some action
- **Charge (pre-peak):** Minimum 66% of max_power_w to avoid wasting surplus PV
- **Charge (cheap):** No minimum, always max when triggered

### Division by Zero Protection

- `_evening_peak_excess_setpoint`: Uses `max(hours_remaining, 0.083)` (5 minutes)
- Prevents infinite power when window is very small

### Null Handling

- All price lookups return None if data unavailable
- All entity reads fall back to defaults
- Strategy continues with available data

### Clamping

- All setpoints clamped to `[min, max_power_w]`
- SOC values naturally bounded by `[0, 100]` from sensors

---

## Mathematical Properties

### Self-Correcting Nature

All setpoints are calculated based on **current** SOC and prices, not target SOC. This means:

1. If actual charge rate < calculated rate (due to losses, PV contribution, etc.):
   - SOC increases slower than expected
   - Next cycle recalculates with new SOC
   - New setpoint is higher to compensate

2. If actual discharge rate < calculated rate:
   - SOC decreases slower than expected
   - Next cycle recalculates with new SOC
   - New setpoint is higher to compensate

**Result:** The strategy automatically adjusts to real-world conditions without explicit feedback loops.

### Efficiency Optimization

The adaptive spread window optimizes for inverter efficiency:

- Copper losses ≈ I²R (scale with current squared)
- Half power ≈ 1/4 the losses of full power
- Spreading over more hours = lower current = lower losses
- Minimum window prevents excessively low power (which has fixed overhead)

**Optimal window:** The contiguous price run, floored at minimum that balances overhead vs. loss reduction.

---

## See Also

- [Configuration Reference](configuration/apps-yaml.md) — Parameters used in these formulas
- [Strategy Priority Chain](../../explanation/strategy-priority-chain.md) — When each algorithm is used
- [Adaptive Spread Windows](../../explanation/adaptive-spread-windows.md) — Deep dive on window sizing
- [Arbitrage Margin](../../explanation/arbitrage-margin.md) — How the margin calculation works
