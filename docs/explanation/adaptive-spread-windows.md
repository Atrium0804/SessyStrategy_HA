# Adaptive Spread Windows

## Overview

**Adaptive spread windows** are a key efficiency feature of SessyStrategy that automatically adjusts the power level (and thus the charging/discharging rate) based on how long favorable price conditions are expected to last. This ensures the battery operates in its most efficient range while still achieving the desired state-of-charge (SOC) transitions within the available time.

---

## Purpose

### The Efficiency Problem

Battery inverters have **non-linear efficiency characteristics**:

- **Copper losses** in the inverter and wiring scale approximately with the **square of current**
- At half power, losses are roughly **4× lower per watt** than at full power
- Operating at lower power levels significantly improves round-trip efficiency

### The Control Challenge

Without adaptive windows, you face a trade-off:
- **Fixed short window:** High power → fast SOC change → high losses → poor efficiency
- **Fixed long window:** Low power → slow SOC change → may not complete before conditions change

### The Solution

Adaptive spread windows **dynamically size the window** based on actual price data:
- Long favorable price periods → wider window → lower power → higher efficiency
- Brief favorable periods → narrower window → higher power → complete the transition
- Minimum window floor (`min_window_h`) prevents excessively high power

---

## Algorithm

### Core Function: `_contiguous_price_hours`

This helper method counts how many consecutive upcoming hours (including the current hour) the price stays past a threshold.

```python
def _contiguous_price_hours(self, threshold: float, above: bool) -> int:
    """
    Count consecutive upcoming hours whose raw price stays past threshold.
    - above=True: count hours where price > threshold
    - above=False: count hours where price < threshold
    Returns at least 1.
    """
```

**Algorithm:**
1. Get the price dictionary from the energy price sensor
2. Start from the current hour
3. Iterate forward through upcoming hours (up to 48 hours for tomorrow's data)
4. For each hour, check if price is above/below threshold
5. Stop at first hour that crosses back
6. Return count (minimum 1)

### Spread Window Calculation: `_spread_window_h`

This method wraps the contiguous hours with a floor:

```python
def _spread_window_h(self, threshold: float, above: bool) -> float:
    """
    Adaptive spread window in hours: contiguous run of hours price stays
    past threshold, floored at min_window_h.
    """
    run_h = self._contiguous_price_hours(threshold, above)
    return max(run_h, self.min_window_h)
```

**Key insight:** The window is **floored**, not capped. This ensures:
- Minimum efficiency even for brief price spikes
- No upper limit — if prices stay favorable for 10 hours, use all 10

---

## Efficiency Benefits

### Mathematical Benefit

For a given energy transfer (ΔE):

```
Power (P) = ΔE / window_h
Losses (L) ∝ P² × window_h = (ΔE² / window_h²) × window_h = ΔE² / window_h
```

**Losses are inversely proportional to window size!**

| Window Size | Power | Relative Loss | Efficiency Gain |
|-------------|--------|---------------|-----------------|
| 1 hour | Full | 100% | Baseline |
| 2 hours | Half | 25% | 4× better |
| 4 hours | Quarter | 6.25% | 16× better |
| 8 hours | 1/8 | 1.56% | 64× better |

### Real-World Impact

For a 5 kWh battery with 90% round-trip efficiency:

**Scenario: Charge 5 kWh**
- Window = 1h, Power = 5000W
  - Losses: ~500 Wh (10%)
  - Energy stored: 4500 Wh
  
- Window = 2h, Power = 2500W
  - Losses: ~125 Wh (2.5%)
  - Energy stored: 4875 Wh (+7.5% more energy)

- Window = 4h, Power = 1250W
  - Losses: ~31 Wh (0.625%)
  - Energy stored: 4969 Wh (+9.3% more energy)

**Over a year with 100 charge cycles:**
- 1h window: 50 kWh lost
- 4h window: 3.1 kWh lost
- **Savings: 46.9 kWh/year**

---

## Usage in Priority Branches

### Priority 1: Price-Spike Discharge

**Window calculation:**
```python
window_h = self._spread_window_h(price_discharge, above=True)
```

**Behavior:**
- Counts how many consecutive hours price stays > `price_discharge`
- Floor: `min_window_h` (default: 2.0 hours)
- Discharges available energy (SOC - soc_floor) over this window

**Example:**
```
Hour: 18:00, SOC: 80%, soc_floor: 20%
Prices: [18:00=€0.46, 19:00=€0.52, 20:00=€0.41, 21:00=€0.25]
price_discharge: €0.39

Contiguous hours > €0.39: 2 (18:00, 19:00)
Window: max(2, 2.0) = 2.0 hours
Available: (80-20)/100 × 5000 = 3000 Wh
Discharge power: 3000/2 = 1500 W
```

**Result:** Gentle 1500W discharge over 2 hours, not 3000W dump in 1 hour.

### Priority 2: Cheap/Negative Price Charge

**Window calculation:**
```python
window_h = self._spread_window_h(price_charge, above=False)
```

**Behavior:**
- Counts how many consecutive hours price stays < `price_charge`
- Floor: `min_window_h` (default: 2.0 hours)
- However, **always charges at max_power_w** when SOC < cheap_soc_target

**Note:** The window is calculated but not used for power determination in P2. The cheap charge branch prioritizes **filling the battery quickly** to capture the cheap energy opportunity, since these windows can be brief and valuable.

**Example:**
```
Hour: 03:00, SOC: 40%, cheap_soc_target: 100%
Prices: [03:00=-€0.15, 04:00=-€0.12, 05:00=€0.02]
price_charge: -€0.10

Contiguous hours < -€0.10: 2 (03:00, 04:00)
Window: max(2, 2.0) = 2.0 hours
Charge power: max_power_w (2200 W)
```

**Rationale:** For cheap/negative prices, the priority is capturing as much energy as possible while the opportunity lasts, even at higher losses.

---

## Configuration

### `min_window_h` Parameter

**Default:** 2.0 hours

**Purpose:** Sets the minimum spread window to prevent excessively high power levels.

**Tuning considerations:**

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.5h | Very short window, high power | Aggressive strategy, accept higher losses for faster response |
| 1.0h | Moderate window | Balanced approach |
| 2.0h | Default, good efficiency | Recommended for most users |
| 4.0h | Long window, low power | Maximum efficiency, but may not complete SOC changes |

**Trade-offs:**
- **Lower values:** More responsive to brief price opportunities, but higher losses
- **Higher values:** Better efficiency, but may not fully utilize brief price spikes

### Relation to Battery Specifications

The optimal `min_window_h` depends on your battery capacity:

```
Optimal min_window_h ≈ capacity_wh / max_power_w
```

For default values:
- Capacity: 5000 Wh
- Max power: 2200 W
- Natural time: 5000/2200 ≈ 2.3 hours
- **Recommended min_window_h: 2.0-2.5 hours**

For larger batteries:
- Capacity: 10000 Wh, Max power: 3500 W
- Natural time: 10000/3500 ≈ 2.9 hours
- **Recommended min_window_h: 2.5-3.0 hours**

---

## Edge Cases

### Brief Price Spikes (1 Hour)

**Scenario:** Price spikes above threshold for only 1 hour.

**Behavior:**
```
Contiguous hours: 1
Window: max(1, 2.0) = 2.0 hours (floor applied)
Power: available_wh / 2.0
```

**Result:** The discharge is spread over 2 hours even though the spike is only 1 hour. This means:
- Hour 1 (spike): Full discharge at calculated power
- Hour 2 (below threshold): Continue discharging at same power

**Economic impact:** Hour 2 discharge happens at below-threshold prices, which is suboptimal. However:
- The efficiency gain from lower power outweighs the price difference
- The alternative (discharging at full power for 1 hour) would have much higher losses

### Very Long Favorable Periods

**Scenario:** Price stays above threshold for 8+ hours.

**Behavior:**
```
Contiguous hours: 8
Window: max(8, 2.0) = 8.0 hours
Power: available_wh / 8.0
```

**Result:** Very low power discharge over many hours.

**Benefit:** Maximum efficiency, but the battery may reach soc_floor before the period ends, at which point the setpoint goes to 0W (see `_discharge_setpoint` method).

### Missing Price Data

**Scenario:** Price data unavailable or incomplete.

**Behavior:**
```
_contiguous_price_hours returns 1 (minimum)
Window: max(1, min_window_h) = min_window_h
```

**Result:** Uses the configured minimum window, providing a safe default.

---

## Examples

### Example 1: Brief Evening Spike

```
Time: 19:00-20:00
Prices: [19:00=€0.45, 20:00=€0.25, 21:00=€0.18]
SOC: 85%, soc_floor: 20%
capacity_wh: 5000
min_window_h: 2.0

Calculation:
- Contiguous hours > €0.39: 1 (only 19:00)
- Window: max(1, 2.0) = 2.0 hours
- Available: (85-20)/100 × 5000 = 3250 Wh
- Power: 3250 / 2.0 = 1625 W

Behavior:
- 19:00: Discharge at 1625 W (price €0.45 > €0.39) ✓
- 20:00: Continue at 1625 W (price €0.25 < €0.39, but window active)
- 20:05: Re-evaluate, spike over, return to P5 (grid 0W)

Efficiency: 1625W is ~27% of max power → ~12× lower losses per watt vs full power
```

### Example 2: Extended Peak

```
Time: 17:00-21:00
Prices: [17:00=€0.42, 18:00=€0.55, 19:00=€0.60, 20:00=€0.48, 21:00=€0.35]
SOC: 90%, soc_floor: 20%
capacity_wh: 5000
min_window_h: 2.0

Calculation (at 17:00):
- Contiguous hours > €0.39: 4 (17:00-20:00)
- Window: max(4, 2.0) = 4.0 hours
- Available: (90-20)/100 × 5000 = 3500 Wh
- Power: 3500 / 4.0 = 875 W

Behavior:
- 17:00-20:00: Discharge at 875 W
- SOC at 20:00: 90 - (875×4)/5000×100 = 72.5%
- 20:00: Price drops to €0.48, still > €0.39, window recalculated
  - New contiguous: 1 hour (only 20:00)
  - New window: max(1, 2.0) = 2.0 hours
  - New power: (72.5-20)/100 × 5000 / 2.0 = 1312.5 W
- 22:00: SOC reaches ~20%, setpoint goes to 0W

Efficiency: 875W is ~40% of max power → excellent efficiency
```

### Example 3: All-Day Cheap (Weekend)

```
Time: Full day
Prices: All hours < -€0.05
SOC: 30%, cheap_soc_target: 100%
capacity_wh: 5000
min_window_h: 2.0

Calculation (at 00:00):
- Contiguous hours < -€0.10: 24 hours
- Window: max(24, 2.0) = 24.0 hours
- But P2 always uses max_power_w for charging
- Power: 2200 W (max)

Behavior:
- Charge at 2200 W until SOC reaches 100%
- Time to full: (100-30)/100 × 5000 / 2200 ≈ 1.59 hours
- After reaching 100%: Hold at grid 0W

Note: Even though the window is 24 hours, P2 prioritizes fast charging
```

---

## Integration with Seasonal Operation

The `min_window_h` parameter can be seasonally adjusted, though this is not currently implemented as a separate winter/summer parameter. The winter-specific overrides include:

- `prepeak_window_h_winter`: Different spread window for pre-peak charging
- But not `min_window_h_winter` (uses base value)

**Recommendation:** If you experience different price patterns in summer vs winter, consider:
- Lower `min_window_h` in winter (more brief spikes, need faster response)
- Higher `min_window_h` in summer (longer, gentler price variations)

Or create separate seasonal overrides if this becomes important for your use case.

---

## See Also

- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — Where adaptive windows are used
- [apps.yaml Configuration](../reference/configuration/apps-yaml.md) — min_window_h and related parameters
- [Algorithms Reference](../reference/algorithms.md) — Mathematical details of the spread calculations
- [Tune Price Thresholds](../how-to/tune-price-thresholds.md) — Adjusting thresholds that affect window calculations
