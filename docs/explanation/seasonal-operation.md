# Seasonal Operation

## Overview

**Seasonal operation** allows SessyStrategy to automatically adapt its behavior based on the time of year. The strategy recognizes that energy price patterns, solar generation, and household energy usage vary significantly between summer and winter, and adjusts its parameters accordingly.

The seasonal mode can be set to `auto`, `summer`, or `winter`. In `auto` mode, the strategy **infers the season** from the hour of the day's minimum raw energy price, providing hands-free seasonal adaptation.

---

## Season Modes

### Mode Options

| Mode | Description | Behavior |
|------|-------------|----------|
| `auto` | Automatic inference | Determine season from price pattern |
| `summer` | Explicit summer mode | Use summer-specific parameters |
| `winter` | Explicit winter mode | Use winter-specific parameters |

### Configuration

The seasonal mode is configured in `apps.yaml`:

```yaml
sessy_strategy:
  season_mode: auto  # auto | summer | winter
  season_day_start: 8      # Start of daytime (hour)
  season_day_end: 18       # End of daytime (hour)
  season_auto_fallback: winter  # Fallback if inference fails
```

Additionally, the mode can be controlled live via an `input_select` entity:

```yaml
season_mode_entity: input_select.sessy_season_mode
```

---

## Season Inference Logic

### The Core Principle

The strategy infers season based on a simple but effective heuristic:

> **Summer:** The day's minimum price occurs during daytime (solar generation hours)
> **Winter:** The day's minimum price occurs during nighttime (no solar generation)

### Implementation: `_infer_season_from_price_minimum`

```python
def _infer_season_from_price_minimum(self) -> str | None:
    """
    Infer season from today's lowest raw price hour.
    If the minimum is during daytime [season_day_start, season_day_end),
    treat it as summer; otherwise winter.
    """
    min_hour, _ = self._daily_min_price_hour_and_value()
    if min_hour is None:
        return None
    
    if self.season_day_start <= min_hour < self.season_day_end:
        return "summer"
    return "winter"
```

### The Logic

1. **Find minimum price hour:** Scan all 24 hours of today's price data to find the hour with the lowest raw price
2. **Check if it's daytime:** Compare the minimum hour against `season_day_start` and `season_day_end`
3. **Determine season:**
   - If minimum is between `season_day_start` and `season_day_end` → **summer**
   - Otherwise → **winter**

### Why This Works

**Summer pattern:**
- Solar generation peaks during daytime (8:00-18:00)
- High solar → low net demand → low prices during the day
- Prices typically dip to their lowest point around midday when PV is maximum
- **Minimum price is during daytime**

**Winter pattern:**
- Little to no solar generation
- Daytime prices are moderate to high (heating demand)
- Overnight prices are typically lowest (low demand, no solar)
- **Minimum price is during nighttime**

### Example Price Patterns

**Summer Day:**
```
Hour: 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
Price:0.30 0.25 0.20 0.15 0.12 0.10 0.08 0.05 0.02 0.01 -0.02 -0.05 -0.08 -0.07 -0.05 -0.02 0.02 0.05 0.08 0.12 0.18 0.25 0.30 0.35
                                                  ^
                                          Minimum at 12:00 (daytime)
                                          Inferred: SUMMER
```

**Winter Day:**
```
Hour: 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
Price:0.15 0.12 0.10 0.08 0.05 0.03 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.40 0.45 0.50 0.45 0.40 0.35 0.30 0.25 0.20 0.18 0.15
       ^
   Minimum at 03:00 (nighttime)
   Inferred: WINTER
```

---

## Season-Specific Overrides

When the active season is `winter`, certain parameters can be overridden with winter-specific values:

### Available Winter Overrides

| Parameter | Default (All Seasons) | Winter Override | Purpose |
|-----------|---------------------|-----------------|---------|
| `soc_floor` | 0% | `soc_floor_winter` | Higher floor in winter for heating reserve |
| `prepeak_start` | 16:00 | `prepeak_start_winter` | Earlier pre-peak window in winter |
| `prepeak_end` | 18:00 | `prepeak_end_winter` | Later pre-peak window in winter |
| `prepeak_window_h` | 2.0h | `prepeak_window_h_winter` | Wider charge window in winter |

### Configuration Example

```yaml
sessy_strategy:
  # Base values (used in summer and when winter overrides are not set)
  soc_floor: 0
  prepeak_start: 16
  prepeak_end: 18
  prepeak_window_h: 2.0
  
  # Winter-specific overrides
  soc_floor_winter: 30        # Keep 30% reserve in winter
  prepeak_start_winter: 14   # Start pre-peak charge earlier
  prepeak_end_winter: 18      # End at same time
  prepeak_window_h_winter: 4.0  # Spread charge over 4 hours
```

### How Overrides Are Applied

The `_seasonal_value` helper method resolves the appropriate value:

```python
def _seasonal_value(self, base_value, active_season: str, winter_override):
    if active_season == "winter" and winter_override is not None:
        return winter_override
    return base_value
```

**Usage in code:**
```python
soc_floor = self._seasonal_value(soc_floor, active_season, self.soc_floor_winter)
prepeak_start = self._seasonal_value(self.prepeak_start, active_season, self.prepeak_start_winter)
prepeak_end = self._seasonal_value(self.prepeak_end, active_season, self.prepeak_end_winter)
prepeak_window_h = self._seasonal_value(self.prepeak_window_h, active_season, self.prepeak_window_h_winter)
```

---

## Season Mode Resolution

### Priority Order

The strategy resolves the active season in the following priority:

1. **Live entity override** (if `season_mode_entity` is configured)
2. **Explicit mode** (if `season_mode` is `summer` or `winter`)
3. **Inferred from price minimum** (if `season_mode` is `auto`)
4. **Fallback** (if inference fails, uses `season_auto_fallback`)

### Implementation: `_active_season_mode`

```python
def _active_season_mode(self) -> str:
    mode = self.season_mode
    
    # Check live entity override
    if self.season_mode_entity:
        mode_state = self.get_state(self.season_mode_entity)
        if isinstance(mode_state, str):
            mode = mode_state.strip().lower()
    
    # If explicitly set, use it
    if mode in ("summer", "winter"):
        return mode
    
    # Otherwise, infer from price pattern
    inferred = self._infer_season_from_price_minimum()
    if inferred:
        return inferred
    
    # Final fallback
    return "summer" if self.season_auto_fallback == "summer" else "winter"
```

---

## Daylight Detection Parameters

### `season_day_start` and `season_day_end`

These parameters define what the strategy considers "daytime" for season inference.

**Default values:**
- `season_day_start`: 8 (08:00)
- `season_day_end`: 18 (18:00)

**Interpretation:** Daytime is from 08:00 (inclusive) to 18:00 (exclusive).

### Tuning Daylight Parameters

Adjust these based on your location and solar patterns:

| Location | Recommended Daylight Hours | Notes |
|----------|---------------------------|-------|
| Netherlands | 8:00-18:00 | Default, good for Northern Europe |
| Southern Europe | 7:00-19:00 | Longer summer days |
| Nordic countries | 7:00-18:00 | Shorter winter days |
| Custom | Match your solar generation | Use local sunrise/sunset data |

**Configuration:**
```yaml
sessy_strategy:
  season_day_start: 7    # Earlier sunrise
  season_day_end: 19     # Later sunset
```

---

## Fallback Logic

### When Inference Fails

The price-based inference can fail if:
- Price data is unavailable
- Price data is incomplete
- All prices are missing or invalid

In these cases, the strategy falls back to `season_auto_fallback`.

**Default:** `winter`

**Rationale:** Winter is the more conservative fallback:
- Higher `soc_floor` (if configured) provides energy reserve
- Earlier pre-peak window ensures battery is charged for evening
- More robust for handling edge cases

**Configuration:**
```yaml
sessy_strategy:
  season_auto_fallback: winter  # or "summer"
```

---

## Seasonal Behavior Differences

### Summer Operation

**Characteristics:**
- High solar generation during daytime
- PV typically fills battery naturally
- Lower household energy demand (no heating)
- Price minimum usually during midday (high PV)

**Strategy behavior:**
- Pre-peak window: 16:00-18:00 (2 hours)
- SOC floor: Typically 0-20%
- Battery fills naturally from PV during the day
- Discharge during evening peak (18:00-22:00)
- Cheap overnight charging is rare (high PV usually keeps battery full)

**Typical SOC trajectory:**
- Morning: ~20-30% (after overnight consumption)
- Afternoon: 90-100% (filled by PV)
- Evening: 20-40% (discharged during peak)

### Winter Operation

**Characteristics:**
- Little to no solar generation
- Higher household energy demand (heating)
- Price minimum usually overnight (low demand)
- Must actively charge battery from grid

**Strategy behavior:**
- Pre-peak window: 14:00-18:00 (4 hours, if configured)
- SOC floor: Typically 30% (heating reserve)
- Battery must be charged from grid overnight or during cheap hours
- Discharge during morning and evening peaks
- Cheap overnight charging is primary charge opportunity

**Typical SOC trajectory:**
- Early morning: ~40-60% (after overnight charging if cheap)
- Afternoon: 70-90% (topped up during pre-peak)
- Evening: 30-50% (discharged during peak)
- Late night: 30-40% (conserved for morning heating)

---

## Examples

### Example 1: Summer Day with Solar

```
Date: July 15
Prices: Minimum at 13:00 (€-0.08)
season_mode: auto
season_day_start: 8
season_day_end: 18

Inference:
- Minimum price hour: 13:00
- 8 <= 13 < 18: True
- Active season: SUMMER

Behavior:
- Pre-peak window: 16:00-18:00
- soc_floor: 0% (base value)
- Battery fills naturally from PV to ~90-100%
- Discharge during evening peak (18:00-22:00) if price > €0.39
```

### Example 2: Winter Day without Solar

```
Date: January 15
Prices: Minimum at 03:00 (€0.05)
season_mode: auto
season_day_start: 8
season_day_end: 18

Inference:
- Minimum price hour: 03:00
- 8 <= 3 < 18: False
- Active season: WINTER

Behavior:
- Pre-peak window: 14:00-18:00 (winter override)
- soc_floor: 30% (winter override)
- Battery charges from grid during cheap overnight hours
- Pre-peak charge to reach 70% before evening
- Discharge during evening peak (18:00-22:00)
```

### Example 3: Manual Season Override

```
Date: Any
season_mode: winter (explicit)
season_mode_entity: input_select.sessy_season_mode

User sets input_select to "summer"

Resolution:
- mode from entity: "summer"
- Active season: SUMMER (entity override takes priority)

Behavior:
- Uses summer parameters regardless of price pattern
- Useful for testing or overriding automatic inference
```

---

## Winter-Specific Considerations

### Higher SOC Floor

**Why:** In winter, with higher heating loads and lower PV generation, it's prudent to maintain a higher minimum SOC to ensure you always have energy available for morning heating demand.

**Recommendation:**
- Summer: 0-20%
- Winter: 20-30% (or higher for cold climates)

### Earlier Pre-Peak Window

**Why:** In winter, the evening peak often starts earlier (17:00-18:00) as people return home and heating demand increases. The earlier pre-peak window ensures the battery is charged before this demand surge.

**Recommendation:**
- Summer: 16:00-18:00 (2 hours)
- Winter: 14:00-18:00 (4 hours)

### Wider Pre-Peak Window

**Why:** With lower PV generation in winter, charging must happen over a longer period to reach the target SOC. The wider window also allows for gentler charging, improving efficiency.

**Recommendation:**
- Summer: 2.0 hours
- Winter: 4.0 hours

### Arbitrage Margin Considerations

**Winter challenge:** In winter, you might find yourself:
- Charging at €0.46/kWh (import = €0.57)
- Discharging at €0.47/kWh (import equivalent = €0.58)
- Margin: Only €0.01/kWh after surcharge

**Solution:** The `min_arbitrage_margin` (€0.05) prevents this uneconomic churning by requiring a minimum raw price spread of €0.05 before pre-peak charging is allowed.

**Note:** The surcharge cancels out in the arbitrage calculation, so raw prices are compared directly.

---

## Status and Monitoring

The active season is published in the strategy status sensor:

```yaml
sensor.sessy_strategy_status
  state: "summer"  # or "winter"
  attributes:
    active_season: "summer"
    season_mode_source: "auto"  # or "entity" if from live selector
```

### Checking Season in Logs

The strategy logs season changes:

```
INFO sessy_strategy: Season mode active: summer
INFO sessy_strategy: Season mode active: winter
```

---

## See Also

- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — How seasons affect priority behavior
- [Price Basis: Raw vs Import](../explanation/price-basis-raw-vs-import.md) — Understanding price calculations used in inference
- [Adaptive Spread Windows](../explanation/adaptive-spread-windows.md) — How pre-peak window affects charging
- [Configure Seasonal Mode](../how-to/configure-seasonal-mode.md) — Step-by-step guide to setting up seasons
- [apps.yaml Configuration](../reference/configuration/apps-yaml.md) — All season-related parameters
- [Status Sensor Attributes](../reference/status-sensor-attributes.md) — Season information in status
