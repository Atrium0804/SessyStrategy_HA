---
title: Tune Price Thresholds
doc_type: how-to
problem: "How do I change charge/discharge prices?"
solution: "Calculate and configure optimal price thresholds for your energy costs"
audience: users
tags:
  - configuration
  - pricing
  - thresholds
  - optimization
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Tune Price Thresholds

**Problem:** You want to change the price thresholds that determine when your battery charges (buys cheap energy) and discharges (sells expensive energy) to better match your energy costs and usage patterns.

**Solution:** Calculate optimal `price_discharge` and `price_charge` thresholds based on your actual energy costs, then configure them either statically in `apps.yaml` or dynamically via live tuning entities.

---

## 📚 Related Documentation

- [Price Basis: Raw vs Import Explained](../explanation/price-basis-raw-vs-import.md)
- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [Live Tuning Entities](../reference/live-tuning-entities.md)

---

## 🎯 Understanding Price Thresholds

### What Price Thresholds Control

SessyStrategy uses two primary price thresholds to make charging decisions:

| Threshold | Purpose | Direction | Priority |
|-----------|---------|-----------|----------|
| `price_discharge` | Trigger for selling stored energy | Discharge when **raw price > threshold** | Priority 1 |
| `price_charge` | Trigger for buying cheap energy | Charge when **raw price < threshold** | Priority 2 |

### Raw vs Import Price Basis

**Critical Concept:** All price thresholds in SessyStrategy work with **raw energy prices** (export prices), NOT import prices.

- **Raw price**: The price you get when exporting energy to the grid
- **Import price**: Raw price + surcharge (taxes, fees) — what you pay when importing
- **Surcharge**: The difference between import and export prices (default: €0.11/kWh for Netherlands)

```
Import Price = Raw Price + Surcharge
```

### Default Values

```yaml
# Default configuration in sessy_strategy.py
price_discharge: 0.39      # Raw price threshold for discharging
price_charge: -0.10       # Raw price threshold for charging (negative = very cheap)
surcharge: 0.11           # Import surcharge
```

**Equivalent import price thresholds:**
- Discharge: 0.39 + 0.11 = **€0.50/kWh import price**
- Charge: -0.10 + 0.11 = **€0.01/kWh import price**

---

## ✅ Solution Steps

### Step 1: Know Your Surcharge

The surcharge is the additional cost per kWh when importing vs. exporting. This varies by country, provider, and contract.

**What to do:** Find your actual surcharge value.

**How to do it:**

1. **Check your energy contract** — look for:
   - Energy tax (energiebelasting)
   - Grid fees (netbeheerkosten)
   - Other mandatory charges

2. **Common values by country:**
   | Country | Typical Surcharge | Notes |
   |---------|------------------|-------|
   | Netherlands | €0.10-0.15/kWh | Includes energy tax + grid fees |
   | Belgium | €0.08-0.12/kWh | Varies by region |
   | Germany | €0.05-0.10/kWh | Lower grid fees |
   | UK | £0.05-0.10/kWh | Ofgem price cap includes some fees |

3. **Configure in apps.yaml:**
   ```yaml
   sessy_strategy:
     module: sessy_strategy
     class: SessyStrategy
     surcharge: 0.11  # Set to your actual surcharge
   ```

**Expected result:** All import price calculations will use your actual surcharge.

### Step 2: Determine Your Break-Even Points

#### Discharge Threshold (`price_discharge`)

**When to discharge:** When the value of energy you're exporting is higher than what you'd save by keeping it in the battery.

**Break-even calculation:**
```
Discharge when: Raw Price > Your Break-Even Export Price
```

**What determines your break-even?**
- **Battery round-trip efficiency**: Typically 90-95% (5-10% loss when charging/discharging)
- **Your alternative value**: What you'd otherwise do with the stored energy
- **Simple rule**: Discharge when raw price > your import price equivalent

**Example calculations:**

| Scenario | Break-even Raw Price | Import Equivalent |
|----------|---------------------|------------------|
| Discharge to avoid €0.50 import | 0.50 - 0.11 = **0.39** | €0.50/kWh |
| Discharge to avoid €0.60 import | 0.60 - 0.11 = **0.49** | €0.60/kWh |
| Discharge to avoid €0.45 import | 0.45 - 0.11 = **0.34** | €0.45/kWh |

**Recommendation:** Set `price_discharge` to **€0.05-0.10 below** your typical peak import price minus surcharge for a safety margin.

#### Charge Threshold (`price_charge`)

**When to charge:** When the cost of energy is so low that it's worth storing for later use.

**Break-even calculation:**
```
Charge when: Raw Price < Your Break-Even Charge Price
```

**What determines your break-even?**
- **Your export value**: What you get when selling stored energy later
- **Battery losses**: Account for 5-10% efficiency loss
- **Opportunity cost**: What you could have done with the money instead

**Example calculations:**

| Scenario | Break-even Raw Price | Import Equivalent |
|----------|---------------------|------------------|
| Charge when export > €0.40 later | 0.40 - 0.11 = **0.29** | €0.40/kWh |
| Charge when export > €0.35 later | 0.35 - 0.11 = **0.24** | €0.35/kWh |
| Charge with negative prices | **-0.10** to **-0.20** | €-0.10 to -0.20/kWh |

**For negative prices:** These are "pay to use" — you get paid to consume energy. Always charge during negative prices unless your battery is full.

**Recommendation:** 
- **Normal conditions**: Set `price_charge` to **€0.10-0.20** (raw) — charge when you expect to export at > €0.21-0.31 later
- **Aggressive**: Set to **€0.00-0.10** (raw) — charge more frequently
- **Conservative**: Set to **-0.10-0.00** (raw) — only charge during very cheap periods

### Step 3: Set Your Thresholds in apps.yaml

**Static configuration (requires AppDaemon restart):**

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  
  # Your energy costs
  surcharge: 0.11  # Your actual surcharge in €/kWh
  
  # Price thresholds (raw prices)
  price_discharge: 0.39  # Discharge when raw > €0.39 (import > ~€0.50)
  price_charge: -0.10    # Charge when raw < -€0.10 (very cheap/negative)
```

**Verification tip:** After setting, check that:
- Import equivalent for discharge: 0.39 + 0.11 = €0.50 ✓
- Import equivalent for charge: -0.10 + 0.11 = €0.01 ✓

### Step 4: Use Live Entities for No-Restart Tuning

**Live configuration (no AppDaemon restart needed):**

1. **Create input_number helpers in Home Assistant:**
   - Go to **Settings > Devices & Services > Helpers**
   - Create these input_numbers:

   | Entity | Name | Min | Max | Step | Unit | Initial |
   |--------|------|-----|-----|------|------|---------|
   | `number.home_battery_price_discharge` | Price Discharge | -1.0 | 2.0 | 0.01 | €/kWh | 0.39 |
   | `number.home_battery_price_charge` | Price Charge | -1.0 | 1.0 | 0.01 | €/kWh | -0.10 |
   | `number.home_battery_min_arbitrage_margin` | Min Arbitrage Margin | 0.0 | 0.5 | 0.01 | €/kWh | 0.05 |

2. **Link to your strategy:**
   ```yaml
   sessy_strategy:
     module: sessy_strategy
     class: SessyStrategy
     
     # Static fallbacks (used if entities unavailable)
     surcharge: 0.11
     price_discharge: 0.39
     price_charge: -0.10
     min_arbitrage_margin: 0.05
     
     # Live entity overrides
     price_discharge_entity: number.home_battery_price_discharge
     price_charge_entity: number.home_battery_price_charge
     min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
   ```

**Expected result:** Changing values in the Home Assistant UI will immediately update the strategy's behavior (after the `rerun_debounce_s` delay, default 2 seconds).

### Step 5: Configure Arbitrage Margin (Optional)

The `min_arbitrage_margin` prevents charging in the pre-peak window if the price spread is too small to be worthwhile.

**What it does:** In Priority 3 (pre-peak charging), the strategy only charges if:
```
(expected_peak_price - current_price) >= min_arbitrage_margin
```

**Default:** €0.05/kWh — requires at least 5 cent spread to justify charging

**Recommendations:**
- **Conservative (€0.08-0.15)**: Only charge when significant savings are guaranteed
- **Moderate (€0.05-0.08)**: Default — good balance
- **Aggressive (€0.02-0.05)**: Charge even with small spreads
- **Very aggressive (€0.00-0.02)**: Charge whenever future prices are higher

**Configuration:**
```yaml
sessy_strategy:
  min_arbitrage_margin: 0.05  # Default
```

---

## 🔍 Verification

To confirm your price thresholds are working correctly:

1. **Check current thresholds in status sensor:**
   - Look at `sensor.sessy_strategy_status` attributes
   - Verify `price_discharge` and `price_charge` match your settings
   - Check `raw_price` and `import_price` are being calculated correctly

2. **Review the logs:**
   ```
   # Look for these patterns in AppDaemon logs:
   Hour=14  SOC=65%  Raw price=0.25000  Import price=0.36000
   
   # Priority 1 trigger (discharge):
   DISCHARGE override: import price 0.500 > 0.50 — battery setpoint 1500W
   
   # Priority 2 trigger (charge):
   CHEAP CHARGE: raw price -0.15000 < -0.10 — battery setpoint -2200W
   
   # Priority 3 skip (insufficient margin):
   PRE-PEAK SKIP: best remaining price 0.350 vs current 0.320 (spread < margin 0.05)
   ```

3. **Test threshold behavior:**
   - **Discharge test**: Wait for a time when `raw_price > price_discharge`
     - Strategy should enter Priority 1 (discharge)
     - Battery setpoint should be positive (discharging)
   - **Charge test**: Wait for a time when `raw_price < price_charge`
     - Strategy should enter Priority 2 (cheap charge)
     - Battery setpoint should be negative (charging)

4. **Test live entity changes (if using):**
   - Change `number.home_battery_price_discharge` to a lower value (e.g., 0.30)
   - Wait 2 seconds for debounce
   - Verify the strategy recalculates and the status sensor shows the new threshold

---

## ⚠️ Common Issues

### Issue 1: Battery Not Discharging During Peak Prices

**Symptom:** Strategy stays in default mode even when prices are high.

**Cause:**
- `price_discharge` is set too high for your current prices
- SOC is at or below `soc_floor`
- Price sensor is not providing current price data

**Fix:**
1. Check current raw price in status sensor
2. Compare with your `price_discharge` threshold
3. Lower `price_discharge` if needed:
   ```yaml
   price_discharge: 0.35  # Lower threshold
   ```
4. Check SOC is above floor:
   ```yaml
   soc_floor: 10  # Ensure battery has charge to discharge
   ```

### Issue 2: Battery Not Charging During Cheap Hours

**Symptom:** Strategy ignores negative or very low prices.

**Cause:**
- `price_charge` is set too low (not triggering)
- SOC is at or above `cheap_soc_target`
- Price sensor data is incorrect

**Fix:**
1. Check current raw price in status sensor
2. Compare with your `price_charge` threshold
3. Raise `price_charge` if needed:
   ```yaml
   price_charge: -0.05  # Higher threshold (triggers more easily)
   ```
4. Check SOC ceiling:
   ```yaml
   cheap_soc_target: 95  # Lower if you want to charge to less than 100%
   ```

### Issue 3: Too Much Charging/Discharging

**Symptom:** Battery cycles too frequently, wearing out the battery.

**Cause:**
- Thresholds are set too close together
- `min_arbitrage_margin` is set too low
- `min_window_h` is too short, causing high power spikes

**Fix:**
1. Increase the spread between thresholds:
   ```yaml
   price_discharge: 0.45  # Higher discharge threshold
   price_charge: -0.15    # Lower charge threshold
   ```
2. Increase arbitrage margin:
   ```yaml
   min_arbitrage_margin: 0.10  # Require larger spread
   ```
3. Increase minimum window:
   ```yaml
   min_window_h: 3.0  # Spread over at least 3 hours
   ```

### Issue 4: Price Calculation Seems Wrong

**Symptom:** Import price doesn't equal raw price + surcharge.

**Cause:**
- Surcharge value is incorrect
- Price sensor provides import prices instead of raw prices

**Fix:**
1. Verify your surcharge value is correct
2. Check if your price sensor is already providing import prices:
   - If so, set `surcharge: 0.00` and adjust thresholds accordingly
3. Test with known values:
   ```
   # If raw_price = 0.30 and surcharge = 0.11
   # import_price should = 0.41
   # If it's 0.30, your sensor provides import prices
   ```

---

## 🎯 Tuning Strategies by User Type

### Strategy for Most Users (Netherlands, Default)

```yaml
sessy_strategy:
  surcharge: 0.11
  price_discharge: 0.39    # Discharge when raw > €0.39 (import > ~€0.50)
  price_charge: -0.10      # Charge when raw < -€0.10
  min_arbitrage_margin: 0.05
```

**Why this works:** Default Dutch energy contracts have ~€0.11 surcharge, and prices typically peak around €0.40-0.50/kWh.

### Strategy for High Energy Cost Regions

```yaml
sessy_strategy:
  surcharge: 0.15        # Higher taxes/fees
  price_discharge: 0.45  # Discharge earlier to avoid higher peaks
  price_charge: -0.15    # Charge more aggressively during cheap hours
  min_arbitrage_margin: 0.08
```

**Best for:** UK, Northern Europe, regions with high energy taxes.

### Strategy for Low Energy Cost Regions

```yaml
sessy_strategy:
  surcharge: 0.08        # Lower taxes/fees
  price_discharge: 0.30  # Discharge at lower threshold
  price_charge: -0.05    # More selective about charging
  min_arbitrage_margin: 0.03
```

**Best for:** Regions with generally lower energy prices and taxes.

### Strategy for Solar-Optimized Users

```yaml
sessy_strategy:
  surcharge: 0.11
  price_discharge: 0.45  # Only discharge at very high prices
  price_charge: -0.20    # Charge aggressively during negative prices
  min_arbitrage_margin: 0.10
  cheap_soc_target: 80   # Don't fill completely during cheap hours
```

**Best for:** Users with solar panels who want to maximize self-consumption.

### Strategy for Grid-Balancing Users

```yaml
sessy_strategy:
  surcharge: 0.11
  price_discharge: 0.35  # Discharge earlier to help grid
  price_charge: 0.00     # Charge at zero or negative prices
  min_arbitrage_margin: 0.02
```

**Best for:** Users who want to support grid stability and get paid for services.

---

## 📝 Best Practices

- ✅ **Do:** Start with default values and monitor for a few days
- ✅ **Do:** Use live entities for easier experimentation
- ✅ **Do:** Consider your actual surcharge, not just estimates
- ✅ **Do:** Leave a safety margin (€0.05-0.10) between thresholds and typical prices
- ✅ **Do:** Check the status sensor regularly to verify thresholds are applied
- ❌ **Don't:** Set thresholds too close together (causes frequent switching)
- ❌ **Don't:** Set `price_charge` above zero unless you understand the implications
- ❌ **Don't:** Set `price_discharge` below zero (battery will never discharge)
- ❌ **Don't:** Forget to account for surcharge in your calculations

---

## 🔗 See Also

- [Price Basis: Raw vs Import Explained](../explanation/price-basis-raw-vs-import.md)
- [Arbitrage Margin Explained](../explanation/arbitrage-margin.md)
- [Strategy Priority Chain Explained](../explanation/strategy-priority-chain.md)
- [How to Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)
- [Debug Strategy Decisions](../how-to/debug-strategy-decisions.md)

---

## 📊 Quick Checklist

- [ ] Determined my actual surcharge value
- [ ] Calculated my break-even discharge threshold
- [ ] Calculated my break-even charge threshold
- [ ] Set thresholds in apps.yaml or created live entities
- [ ] Configured min_arbitrage_margin appropriately
- [ ] Verified thresholds appear in status sensor
- [ ] Tested discharge behavior at high prices
- [ ] Tested charge behavior at low/negative prices
- [ ] Monitored for at least one full day to validate behavior

---

*Last updated: 2026-08-01*