# Price Basis: Raw vs Import

## Overview

The SessyStrategy works with **two different price concepts** that are critical to understanding the strategy logic and configuring thresholds correctly. This document explains the distinction between **raw export prices** and **import prices**, and why the strategy uses raw prices for all threshold comparisons.

---

## The Two Price Types

### Raw Export Price

**Definition:** The price the grid **pays you** for electricity you export (sell back to the grid).

**Source:** This is the value provided by your energy price sensor (e.g., `sensor.sessy_dnhh_energy_price`).

**Characteristics:**
- Directly reflects wholesale market prices
- Can be negative (grid pays you to consume)
- Used for all threshold comparisons in the strategy
- No additional fees or taxes

**Example values:**
- €0.10/kWh (moderate)
- -€0.14/kWh (negative — grid pays you)
- €0.50/kWh (high peak)

### Import Price

**Definition:** The price **you pay** for electricity you import (buy from the grid).

**Calculation:** `import_price = raw_export_price + surcharge`

**Characteristics:**
- Includes energy tax/surcharge (default: €0.11/kWh for Netherlands)
- Always higher than raw price by the surcharge amount
- Represents your actual cost per kWh
- Never negative (even if raw price is negative)

**Example calculation:**
- Raw price: €0.39/kWh
- Surcharge: €0.11/kWh
- Import price: €0.50/kWh

---

## Why Raw Prices Are Used for Thresholds

The strategy uses **raw export prices** for all its threshold comparisons. This is a deliberate design choice with important implications.

### The Surcharge Effect

The surcharge (€0.11/kWh by default) is a **fixed cost** that applies to all imports but not to exports. This means:

```
When you IMPORT:  You pay raw_price + surcharge
When you EXPORT:  You receive raw_price (no surcharge)
```

### Equivalent Import Thresholds

Since the strategy uses raw prices but you care about your actual costs, it's helpful to understand the **import-equivalent** thresholds:

| Strategy Threshold | Raw Price | Import Equivalent | Meaning |
|-------------------|-----------|------------------|---------|
| `price_discharge` | > €0.39 | > €0.50 | Discharge when import would cost more than €0.50 |
| `price_charge` | < -€0.10 | < €0.01 | Charge when import would cost less than €0.01 |

### Why This Works

The strategy's logic is based on **opportunity cost**:

1. **Discharging:** When raw_price > €0.39, the import price is > €0.50. By discharging the battery, you:
   - Avoid paying €0.50+ for grid imports
   - Sell stored energy at €0.39+ (raw)
   - Net benefit: ~€0.11+ per kWh avoided

2. **Charging:** When raw_price < -€0.10, the import price is < €0.01. By charging from grid, you:
   - Buy energy for essentially free (or get paid)
   - Store it for later use when prices are higher
   - Net benefit: Full value of avoided future imports

---

## Surcharge Explanation

### What is the Surcharge?

The surcharge represents **energy taxes and fees** that are added to the raw energy price when you import electricity. In the Netherlands, this is typically €0.11/kWh (as of 2026).

**Components (Netherlands example):**
- Energy tax (energiebelasting)
- Other regulatory fees
- Grid connection costs

### Configuring the Surcharge

The surcharge is configurable in `apps.yaml`:

```yaml
sessy_strategy:
  surcharge: 0.11  # €/kWh - adjust to your local energy taxes
```

**Important:** Update this value to match your local energy taxes and fees.

### Surcharge Impact on Strategy

The surcharge affects:

1. **Import price calculations:** `import_price = raw_price + surcharge` (used in logs)
2. **Threshold interpretation:** All raw price thresholds implicitly include the surcharge in their economic meaning
3. **Arbitrage decisions:** The `min_arbitrage_margin` (€0.05) ensures that price differences are large enough to overcome the surcharge

---

## Threshold Rationale

### Price Discharge Threshold

**Default:** €0.39/kWh (raw)

**Economic meaning:** Discharge when the raw export price exceeds €0.39, which means:
- Import price > €0.50/kWh
- It's cheaper to use stored battery energy than to import from grid
- Selling at €0.39/kWh avoids buying at €0.50/kWh = €0.11/kWh savings

**Tuning considerations:**
- Raise if you want to be more conservative (discharge only at higher prices)
- Lower if you want to be more aggressive (discharge at slightly lower prices)
- Consider your actual import costs and battery round-trip efficiency (~90-95%)

### Price Charge Threshold

**Default:** -€0.10/kWh (raw)

**Economic meaning:** Charge from grid when the raw price drops below -€0.10, which means:
- Import price < €0.01/kWh
- You're essentially being paid €0.10/kWh to consume energy
- Even after accounting for the surcharge, this is extremely cheap energy

**Tuning considerations:**
- Raise (less negative) to charge more often at moderately cheap prices
- Lower (more negative) to only charge at extremely cheap/negative prices
- Consider your battery's round-trip efficiency

---

## Comparison Table

| Scenario | Raw Price | Import Price | Strategy Action | Economic Benefit |
|----------|-----------|--------------|-----------------|------------------|
| Normal day | €0.20 | €0.31 | Default (grid 0W) | Maximize self-consumption |
| Cheap night | -€0.15 | -€0.04 | Charge at max power | Store energy for ~€0.15/kWh |
| Moderate | €0.30 | €0.41 | Default (grid 0W) | Wait for better opportunity |
| Price spike | €0.46 | €0.57 | Discharge toward floor | Avoid €0.57 imports, sell at €0.46 |
| Peak | €0.60 | €0.71 | Discharge toward floor | Avoid €0.71 imports, sell at €0.60 |

---

## Price Basis in Each Priority

### Priority 1: Price-Spike Discharge

- **Comparison:** `raw_price > price_discharge`
- **Raw threshold:** €0.39/kWh
- **Import equivalent:** €0.50/kWh
- **Logic:** Avoid the most expensive imports

### Priority 2: Cheap/Negative Price Charge

- **Comparison:** `raw_price < price_charge`
- **Raw threshold:** -€0.10/kWh
- **Import equivalent:** €0.01/kWh
- **Logic:** Capture energy when it's essentially free or better

### Priority 3: Afternoon Charge

- **Comparison:** Uses **import (buy)** prices for both the current hour and the evening peak
- **Peak-shaving calculation:** `evening_peak_buy_price - current_buy_price >= afternoon_margin`
- **Import margin:** €0.05/kWh
- **Logic:** Top up now at a low afternoon import price to avoid importing at a higher price during the evening peak

**Why import prices for afternoon charge?**

Priority 3 is **peak-shaving, not trading**. Both sides of the comparison are import prices, because the energy you charge now is energy you will **self-consume** during the evening peak instead of importing it from the grid:
```
(evening_peak_raw + surcharge) - (current_raw + surcharge) >= afternoon_margin
```

The surcharge is present on both sides, but it must stay because the decision is about the **actual import cost avoided**. You compare what you would pay to import during the evening peak against what you pay to charge now. If that reduction is at least `afternoon_margin`, charging is worthwhile.

!!! note
    This is deliberately **not** grid trading. When trading (buy to later export), taxes and fees paid on the import are a pure loss. Priority 3 only manages self-consumed energy, so it uses the buy price on both sides. The trading decision (hold vs sell) is Priority 4 and uses `min_arbitrage_margin`.

### Priority 4: Evening Peak Sell-off Discharge

- **Comparison:** `max_remaining_price < price_discharge`
- **Raw threshold:** €0.39/kWh
- **Logic:** Discharge excess if no more expensive spikes are expected

### Priority 5: Default

- **No price comparison**
- **Logic:** Maximize self-consumption regardless of price

---

## Practical Examples

### Example 1: Overnight Cheap Charge

```
Hour: 02:00
Raw price: -€0.14/kWh
Import price: €0.03/kWh (raw + €0.11 - €0.14 = -€0.03, but min €0.00)
SOC: 40%
Threshold: price_charge = -€0.10

Comparison: -€0.14 < -€0.10 = TRUE
Action: Charge at max power (Priority 2)
Benefit: Store energy bought at effectively -€0.14 for later use
```

### Example 2: Evening Peak

```
Hour: 19:00
Raw price: €0.46/kWh
Import price: €0.57/kWh
SOC: 80%
Threshold: price_discharge = €0.39

Comparison: €0.46 > €0.39 = TRUE
Action: Discharge toward soc_floor (Priority 1)
Benefit: Avoid €0.57 imports, sell at €0.46
Net savings: €0.11/kWh
```

### Example 3: Afternoon Charge Decision

```
Hour: 16:30
Current import price: €0.26/kWh (raw €0.15 + €0.11 surcharge)
Evening peak import price: €0.61/kWh (raw €0.50 + €0.11, at 19:00)
SOC: 60%, target_afternoon_charging: 70%
afternoon_margin: €0.05

Peak-shaving check: €0.61 - €0.26 = €0.35 >= €0.05 = PASS
Action: Charge toward target_afternoon_charging (Priority 3)
Benefit: Top up now at €0.26 import instead of importing at €0.61 during the peak
Avoided import cost: €0.35/kWh (minus round-trip losses)
```

---

## Common Questions

### Q: Why not use import prices directly in the strategy?

A: The Sessy integration provides **raw export prices**, not import prices. Additionally, using raw prices with a separate surcharge configuration:
- Matches the data available from the integration
- Makes the strategy portable across regions with different surcharges
- Keeps the threshold values meaningful (raw prices are what you see in the market)

### Q: How do I convert my utility's import prices to raw prices?

A: Subtract your surcharge:
```
raw_price = import_price - surcharge
```

For example, if your utility shows import prices and your surcharge is €0.11:
- Import price €0.50 → Raw price €0.39
- Import price €0.25 → Raw price €0.14

### Q: What if my surcharge is different?

A: Simply update the `surcharge` parameter in `apps.yaml`. All calculations will automatically use the new value. The raw price thresholds remain the same, but their economic meaning changes:

```yaml
# For a region with €0.15 surcharge
surcharge: 0.15
# price_discharge: 0.39 means import > €0.54

# For a region with €0.08 surcharge
surcharge: 0.08
# price_discharge: 0.39 means import > €0.47
```

### Q: Why is the price_charge threshold negative?

A: Negative raw prices mean the grid pays you to consume energy. The threshold of -€0.10 is intentionally negative because:
- It captures both negative prices and very cheap positive prices
- After adding the €0.11 surcharge, -€0.10 raw becomes €0.01 import — essentially free
- More conservative users can raise this to 0 or slightly positive

---

## See Also

- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — How prices trigger different strategies
- [apps.yaml Configuration](../reference/configuration/apps-yaml.md) — All price-related parameters
- [Tune Price Thresholds](../how-to/tune-price-thresholds.md) — How to adjust thresholds for your situation
