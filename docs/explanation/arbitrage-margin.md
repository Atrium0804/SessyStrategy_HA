# Arbitrage Margin

## Overview

The **arbitrage margin** (`min_arbitrage_margin`) is a critical safeguard in the SessyStrategy that prevents uneconomic battery cycling. It ensures that the strategy only charges the battery from the grid when the expected future savings justify the current cost, accounting for round-trip losses and the strategy's own overhead.

---

## Purpose

### The Arbitrage Problem

**Arbitrage** in energy storage means: *buy low, sell high*. For a home battery, this translates to:

1. **Buy (charge):** Purchase electricity from grid at low price
2. **Store:** Keep energy in battery (with some losses)
3. **Sell (discharge):** Use stored energy to avoid buying at high price

**Net benefit:** (Price avoided) - (Price paid) - (Losses)

### The Risk of Churning

Without a margin requirement, the battery might engage in **uneconomic churning**:

```
Example of BAD arbitrage:
- Charge at: €0.46/kWh (import)
- Discharge to avoid: €0.47/kWh (import)
- Margin: €0.01/kWh
- Losses (~5%): €0.023/kWh
- Net result: LOSS of €0.013/kWh
```

This is **worse than doing nothing** — you've cycled the battery, incurred wear, and lost money.

### The Solution

The `min_arbitrage_margin` sets a **minimum price spread** that must be exceeded before the strategy will charge the battery in preparation for a future peak. This ensures that only **economically viable** arbitrage opportunities are pursued.

---

## Configuration

### Parameter

**Name:** `min_arbitrage_margin`

**Type:** Float (€/kWh)

**Default:** 0.05 (€0.05/kWh)

**Configuration:**

```yaml
sessy_strategy:
  min_arbitrage_margin: 0.05  # Minimum €/kWh spread to justify charging
```

**Live tuning:** Can be adjusted via `min_arbitrage_margin_entity` without restarting AppDaemon:

```yaml
min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
```

---

## How It Works

### In Priority 3: Pre-Peak Charge

The arbitrage margin is used in the **pre-peak charge window** (Priority 3) to determine whether charging now to discharge later is economically justified.

**Condition:**
```python
if prepeak_start <= now_hour < prepeak_end:
    if soc >= soc_target:
        # Already at target, no need to charge
        return
    
    # Arbitrage check
    expected_peak = self._max_price_in_window(now_hour, 24)
    if expected_peak is not None and \
            (expected_peak - price) < min_arbitrage_margin:
        # Spread too small, skip charging
        return
    
    # Spread is sufficient, proceed with charging
    charge_w = self._charge_setpoint(soc, soc_target, prepeak_window_h)
    self._set_battery_setpoint(-charge_w)
    return
```

### The Arbitrage Calculation

**Formula:**
```
price_spread = expected_peak_raw - current_raw_price
if price_spread >= min_arbitrage_margin:
    # Good arbitrage opportunity
else:
    # Skip charging, not worth it
```

**Key insight:** The calculation uses **raw prices**, not import prices, because the surcharge cancels out:

```
Actual calculation:
- Buy at: current_raw_price + surcharge
- Avoid buying at: expected_peak_raw + surcharge
- Spread: (expected_peak_raw + surcharge) - (current_raw_price + surcharge)
         = expected_peak_raw - current_raw_price
```

The surcharge terms cancel, so comparing raw prices directly gives the correct economic spread.

---

## Break-Even Calculation

### Understanding the Economics

For arbitrage to be profitable, the **net benefit must be positive**:

```
Net Benefit = (Avoided Cost) - (Purchase Cost) - (Losses)

Where:
- Avoided Cost = expected_peak_raw + surcharge
- Purchase Cost = current_raw_price + surcharge
- Losses = round_trip_efficiency × purchase_cost
```

**Simplified:**
```
Net Benefit = (expected_peak_raw - current_raw_price) × (1 - loss_factor) - overhead
```

### Default Values

| Parameter | Value | Notes |
|-----------|-------|-------|
| `min_arbitrage_margin` | €0.05/kWh | Conservative default |
| Round-trip efficiency | ~90-95% | Battery + inverter losses |
| Loss factor | ~5-10% | 1 - efficiency |

### Economic Justification

With the default €0.05 margin:

```
Example calculation:
- Current raw price: €0.15/kWh
- Expected peak raw: €0.50/kWh
- Spread: €0.35/kWh
- min_arbitrage_margin: €0.05/kWh

Calculation:
- Buy at: €0.15 + €0.11 = €0.26/kWh
- Avoid buying at: €0.50 + €0.11 = €0.61/kWh
- Gross benefit: €0.35/kWh
- Less losses (~5%): €0.013/kWh
- Net benefit: €0.337/kWh

Result: PASS (€0.35 > €0.05)
```

**Marginal case:**
```
- Current raw price: €0.46/kWh
- Expected peak raw: €0.51/kWh
- Spread: €0.05/kWh
- min_arbitrage_margin: €0.05/kWh

Calculation:
- Buy at: €0.46 + €0.11 = €0.57/kWh
- Avoid buying at: €0.51 + €0.11 = €0.62/kWh
- Gross benefit: €0.05/kWh
- Less losses (~5%): €0.003/kWh
- Net benefit: €0.047/kWh

Result: PASS (€0.05 >= €0.05), but very marginal
```

**Rejected case:**
```
- Current raw price: €0.46/kWh
- Expected peak raw: €0.50/kWh
- Spread: €0.04/kWh
- min_arbitrage_margin: €0.05/kWh

Result: SKIP (€0.04 < €0.05)
Rationale: Not worth the battery cycling
```

---

## When Charging is Profitable

### The Profitability Condition

Charging in the pre-peak window is profitable when:

```
expected_peak_raw - current_raw_price >= min_arbitrage_margin
```

This means:
1. The expected peak price must be **at least `min_arbitrage_margin` higher** than the current price
2. The difference must be large enough to cover losses and provide a buffer

### Visual Representation

```mermaid
%%{init: {'theme': 'neutral'}}%%
xychart-beta
    title "Arbitrage Decision Space"
    x-axis "Current Raw Price (€/kWh)" 0 --> 0.60
    y-axis "Expected Peak Raw (€/kWh)" 0 --> 0.60
    
    %% Diagonal line: equal prices (no arbitrage)
    line [0.0, 0.0, 0.6, 0.6] as equal
    text "No arbitrage" at [0.3, 0.25]
    
    %% Margin line: current + margin
    line [0.0, 0.05, 0.55, 0.60] as margin
    text "min_arbitrage_margin = 0.05" at [0.3, 0.35]
    
    %% Regions
    fill [0.0, 0.0, 0.55, 0.05]
    text "SKIP" at [0.2, 0.02]
    
    fill [0.0, 0.05, 0.6, 0.6]
    text "CHARGE" at [0.4, 0.4]
```

**Interpretation:**
- **Above the margin line:** `expected_peak - current >= 0.05` → **CHARGE** (profitable)
- **Below the margin line:** `expected_peak - current < 0.05` → **SKIP** (not profitable)

---

## Example Scenarios

### Scenario 1: Clear Arbitrage Opportunity

```
Time: 16:30
Current raw price: €0.15/kWh
Expected peak (19:00): €0.55/kWh
SOC: 60%, soc_target: 70%
min_arbitrage_margin: €0.05

Arbitrage check:
- Spread: €0.55 - €0.15 = €0.40
- Margin requirement: €0.05
- Result: €0.40 > €0.05 → PASS

Action: Charge toward 70% SOC

Economic analysis:
- Charge cost: €0.15 + €0.11 = €0.26/kWh
- Avoided cost: €0.55 + €0.11 = €0.66/kWh
- Gross benefit: €0.40/kWh
- Less losses (~5%): €0.02/kWh
- Net benefit: €0.38/kWh
```

### Scenario 2: Marginal Arbitrage

```
Time: 15:00
Current raw price: €0.45/kWh
Expected peak (18:00): €0.50/kWh
SOC: 65%, soc_target: 70%
min_arbitrage_margin: €0.05

Arbitrage check:
- Spread: €0.50 - €0.45 = €0.05
- Margin requirement: €0.05
- Result: €0.05 >= €0.05 → PASS (at threshold)

Action: Charge toward 70% SOC

Economic analysis:
- Charge cost: €0.45 + €0.11 = €0.56/kWh
- Avoided cost: €0.50 + €0.11 = €0.61/kWh
- Gross benefit: €0.05/kWh
- Less losses (~5%): ~€0.003/kWh
- Net benefit: €0.047/kWh

Note: Very marginal, but technically profitable
```

### Scenario 3: Rejected Arbitrage

```
Time: 17:00
Current raw price: €0.48/kWh
Expected peak (19:00): €0.51/kWh
SOC: 68%, soc_target: 70%
min_arbitrage_margin: €0.05

Arbitrage check:
- Spread: €0.51 - €0.48 = €0.03
- Margin requirement: €0.05
- Result: €0.03 < €0.05 → SKIP

Action: Hold at grid 0W

Rationale: The €0.03 spread is insufficient to justify battery cycling
```

### Scenario 4: Winter Challenge Case

```
Time: 14:00 (winter)
Current raw price: €0.46/kWh
Expected peak (17:00): €0.48/kWh
SOC: 55%, soc_target: 70%
min_arbitrage_margin: €0.05

Arbitrage check:
- Spread: €0.48 - €0.46 = €0.02
- Margin requirement: €0.05
- Result: €0.02 < €0.05 → SKIP

Rationale: In winter, price spreads can be narrow. The margin
prevents uneconomic churning where you'd lose money on each cycle.
```

---

## Tuning the Arbitrage Margin

### When to Adjust

Consider adjusting `min_arbitrage_margin` if you observe:

| Symptom | Current Margin | Suggested Action | Rationale |
|---------|----------------|------------------|-----------|
| Too much charging at marginal prices | Low (e.g., 0.02) | Increase to 0.05-0.10 | Avoid uneconomic cycles |
| Missing good arbitrage opportunities | High (e.g., 0.15) | Decrease to 0.03-0.05 | Capture more value |
| Battery cycles too often | Any | Increase by 0.02-0.05 | Reduce wear and tear |
| Winter performance poor | Any | Increase to 0.10+ | Wider spreads needed |

### Recommended Values

| Situation | Recommended Margin | Notes |
|-----------|-------------------|-------|
| Conservative (default) | €0.05/kWh | Safe for most users |
| Aggressive | €0.03/kWh | Capture more opportunities, higher risk |
| Very conservative | €0.10/kWh | Only clear arbitrage, miss some opportunities |
| Winter-specific | €0.08-0.12/kWh | Account for lower spreads in winter |
| High-loss systems | €0.07-0.10/kWh | If your system has >10% round-trip losses |

### Regional Considerations

The optimal margin depends on your **local price volatility**:

| Region | Price Volatility | Recommended Margin | Notes |
|--------|------------------|-------------------|-------|
| Netherlands | Moderate | €0.05 | Default works well |
| Nordic countries | Low | €0.03 | Small spreads, need lower margin |
| UK | Moderate-high | €0.05-0.08 | Higher volatility |
| Germany | High | €0.07-0.10 | Significant price swings |
| France | Moderate | €0.05 | Similar to Netherlands |

---

## Integration with Other Parameters

### Relationship with `soc_target`

The arbitrage margin works together with `soc_target` to determine when to charge:

- **High `soc_target`** (e.g., 80%) + **Low margin** (e.g., 0.03): More aggressive charging, higher SOC
- **Low `soc_target`** (e.g., 60%) + **High margin** (e.g., 0.10): More conservative, only clear opportunities

### Relationship with `prepeak_window_h`

The pre-peak window affects how charging is spread:

- **Wider window** (e.g., 4h) + **Low margin**: Charge gently over long period, capture small spreads
- **Narrow window** (e.g., 1h) + **High margin**: Only charge at high power for clear opportunities

### Relationship with Seasonal Overrides

In winter, consider:
- **Higher margin** (e.g., 0.08-0.10): Account for narrower spreads
- **Wider pre-peak window** (e.g., 4h): More time to capture opportunities
- **Higher `soc_target`** (e.g., 80%): More energy for heating demand

---

## Common Questions

### Q: Why not set the margin to zero?

A: A zero margin would mean charging whenever the expected peak is even €0.01 higher than the current price. This leads to:
- **Battery churning:** Constant charging/discharging for minimal benefit
- **Increased wear:** More battery cycles reduce lifespan
- **Loss of money:** Round-trip losses (>5%) exceed the marginal gains
- **Unnecessary complexity:** Small arbitrage opportunities are hard to predict accurately

**Bottom line:** The margin is a **safeguard** against imperfect information and real-world losses.

### Q: How do I know if my margin is set correctly?

A: Monitor your strategy's behavior and outcomes:

1. **Check logs** for arbitrage decisions:
   ```
   PRE-PEAK SKIP: best remaining price 0.48 vs current 0.46 (spread < margin 0.05)
   PRE-PEAK CHARGE: battery setpoint -1200W (SOC 65% → target 70% over 2h)
   ```

2. **Calculate actual outcomes:**
   - Track when you charged and at what price
   - Track when you discharged and what you avoided
   - Calculate net benefit per cycle

3. **Adjust if:**
   - You're consistently skipping opportunities that seem profitable → **lower margin**
   - You're charging for small spreads that end up being uneconomic → **raise margin**

### Q: Does the margin account for battery degradation?

A: No, the margin is purely **economic**. Battery degradation is a separate consideration:

- **Economic margin:** Ensures each cycle is immediately profitable
- **Degradation cost:** Long-term cost of battery wear

**Combined consideration:** If your battery costs €10,000 and has 5,000 cycles, each cycle "costs" ~€2 in degradation. If your margin is €0.05/kWh, you need to save at least €2 worth of energy (40 kWh) per cycle to break even on degradation.

For most home batteries (5-15 kWh), this means:
- **Don't worry about degradation** for the margin calculation
- **The economic margin is sufficient** to justify the wear
- **Only very marginal opportunities** (€0.01-0.02 spreads) might not be worth the long-term degradation cost

### Q: Can I have different margins for different seasons?

A: Currently, the strategy only supports a single `min_arbitrage_margin` value. However, you can:

1. **Use the live entity** (`min_arbitrage_margin_entity`) and manually adjust it per season
2. **Create automation** in Home Assistant to adjust the margin based on season
3. **Adjust other parameters** seasonally (prepeak window, soc_target) to compensate

**Future enhancement:** You could extend the code to support `min_arbitrage_margin_winter` similar to other seasonal overrides.

### Q: What's the relationship between arbitrage margin and the price thresholds?

A: They serve different purposes:

| Parameter | Purpose | When It Applies |
|-----------|---------|-----------------|
| `price_discharge` | Trigger for selling stored energy | P1: Price spike discharge |
| `price_charge` | Trigger for buying cheap energy | P2: Cheap price charge |
| `min_arbitrage_margin` | Minimum spread for pre-peak charging | P3: Pre-peak charge |

**No direct relationship** — they're independent thresholds that each serve a specific purpose in the priority chain.

---

## See Also

- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — Where arbitrage margin is used (P3)
- [Price Basis: Raw vs Import](../explanation/price-basis-raw-vs-import.md) — Understanding the price calculations
- [Seasonal Operation](../explanation/seasonal-operation.md) — How winter affects arbitrage opportunities
- [Tune Price Thresholds](../how-to/tune-price-thresholds.md) — Adjusting all price-related parameters
- [apps.yaml Configuration](../reference/configuration/apps-yaml.md) — All arbitrage-related parameters
- [Algorithms Reference](../reference/algorithms.md) — Mathematical details of arbitrage calculations
