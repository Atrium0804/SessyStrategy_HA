---
title: First Day Operation with SessyStrategy HA
doc_type: tutorial
audience: beginners
prerequisites: 
  - SessyStrategy successfully installed and configured
  - AppDaemon running without errors
  - All required entities available
tags:
  - first-day
  - beginner
  - operation
created: 2026-08-01
last_updated: 2026-08-01
---

# First Day Operation with SessyStrategy HA

**Estimated reading time:** 15 minutes | **Difficulty:** Beginner

---

## 🎯 What You Will Learn

- What to expect during your first day with SessyStrategy
- How the strategy behaves during different times of day
- What normal operation looks like
- How to interpret strategy decisions and entity changes
- When and why the strategy switches between different modes

## 📋 Prerequisites

Before starting this tutorial, ensure you have:

- ✅ **SessyStrategy installed** — Completed [Getting Started Tutorial](getting-started.md)
- ✅ **AppDaemon running** — No errors in the AppDaemon log
- ✅ **All entities available** — Status sensor, SOC sensor, price sensor all show data
- ✅ **Basic monitoring set up** — Ability to watch entity states and logs

## 📚 Related Documentation

- [Getting Started](getting-started.md) — Installation and setup guide
- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — How decisions are made
- [Price Basis: Raw vs Import](../explanation/price-basis-raw-vs-import.md) — Understanding price calculations
- [Debug Strategy Decisions](../how-to/debug-strategy-decisions.md) — Troubleshooting guide
- [Setpoint Types Explained](../explanation/setpoint-types-explained.md) — Battery vs grid setpoints

---

## 🌅 Morning: The Day Begins

### What to Expect

As your first day begins, SessyStrategy will start making decisions based on your battery's current state of charge (SOC) and the current energy price.

### Typical Morning Behavior

**6:00 - 9:00 AM:**
- **SOC Level:** Typically between 20-60% (depending on overnight usage)
- **Price:** Usually moderate to low
- **Strategy:** Most likely `DEFAULT` — grid setpoint 0W
- **Behavior:** Battery absorbs solar, blocks export, grid covers any load shortfall

### What You Should See

1. **Status Sensor:**
   ```
   sensor.sessy_strategy_status = "default"
   active_branch = "default"
   soc = 35.2  # or similar
   raw_price = 0.12345
   import_price = 0.23345
   ```

2. **Strategy Select:** `nom` (grid setpoint mode)

3. **Grid Target:** `0` (blocking export)

4. **Logs:**
   ```
   INFO sessy_strategy: Hour=07  SOC=35%  Raw price=0.12345  Import price=0.23345
   INFO sessy_strategy: DEFAULT: grid setpoint 0W — absorb solar, block export
   ```

### Why This Happens

At moderate prices (below `price_discharge` threshold), the strategy defaults to grid setpoint 0W. This means:
- Any solar production goes to power your home first
- Excess solar goes into the battery (not exported to grid)
- If home load exceeds solar + battery, grid covers the difference
- This avoids the €0.11/kWh round-trip surcharge on exported/imported energy

---

## ☀️ Mid-Morning to Afternoon: Solar Charging

### What to Expect

As the sun rises and your solar panels start producing, the strategy continues to optimize.

### Typical Mid-Morning Behavior

**9:00 AM - 3:00 PM:**
- **SOC Level:** Rising as solar charges the battery
- **Price:** Typically low to moderate during daytime
- **Strategy:** Most likely still `DEFAULT` — grid setpoint 0W
- **Behavior:** All solar energy is directed to battery charging and home consumption

### What You Should See

1. **Status Sensor:**
   ```
   sensor.sessy_strategy_status = "default"
   active_branch = "default"
   soc = 58.7  # rising
   raw_price = 0.08923
   ```

2. **Strategy Select:** `nom` (grid setpoint mode)

3. **Grid Target:** `0`

4. **SOC Sensor:** Gradually increasing as solar charges the battery

5. **Logs:**
   ```
   INFO sessy_strategy: Hour=11  SOC=58%  Raw price=0.08923  Import price=0.19923
   INFO sessy_strategy: DEFAULT: grid setpoint 0W — absorb solar, block export
   ```

### Key Observations

- **SOC rising:** This is normal as solar energy charges the battery
- **Grid target at 0:** Ensures all solar goes to battery/home, no export
- **Efficiency:** This is the most efficient mode — storing solar for later use avoids import costs

### If SOC Reaches Target Early

If your battery fills up before the evening:
- The strategy will continue in DEFAULT mode
- Excess solar will be exported to grid (unavoidable)
- This typically happens on very sunny days with low household consumption

---

## 🌇 Pre-Peak Window: Preparing for Evening

### What to Expect

SessyStrategy has a specific window for topping up the battery before the evening peak.

### Typical Pre-Peak Behavior

**Default: 4:00 - 6:00 PM (Summer: 4:00-6:00 PM, Winter: 2:00-6:00 PM)**

The strategy checks two conditions:
1. **Time window:** Current hour is within `prepeak_start` to `prepeak_end`
2. **SOC below target:** Current SOC < `soc_target` (default 70%)

### What You Should See

**Case A: SOC below target, peak is profitable**
```
INFO sessy_strategy: Hour=16  SOC=62%  Raw price=0.15678  Import price=0.26678
INFO sessy_strategy: PRE-PEAK CHARGE: battery setpoint -850W (SOC 62% → target 70% over 2.0h)
```

- **Status Sensor:** `prepeak_charge`
- **Strategy Select:** `api` (battery setpoint mode)
- **Battery Setpoint:** Negative value (e.g., -850W = charge at 850W)

**Case B: SOC already at target**
```
INFO sessy_strategy: Hour=16  SOC=72%  Raw price=0.15678  Import price=0.26678
INFO sessy_strategy: PRE-PEAK: SOC 72% already at target 70% — holding grid setpoint 0W
```

- **Status Sensor:** `prepeak_full`
- **Strategy Select:** `nom`
- **Grid Target:** `0`

**Case C: Peak not profitable enough**
```
INFO sessy_strategy: Hour=16  SOC=62%  Raw price=0.15678  Import price=0.26678
INFO sessy_strategy: PRE-PEAK SKIP: best remaining price 0.28 vs current 0.15678 (spread < margin 0.05) — holding grid setpoint 0W
```

- **Status Sensor:** `prepeak_skip`
- **Reason:** Expected evening peak price minus current price < `min_arbitrage_margin`

### Why This Matters

The pre-peak charge is **strategic**: it only charges from grid if:
1. Battery SOC is below target
2. The expected evening peak price is significantly higher than current price
3. The margin justifies the charge/discharge cycle (including round-trip losses)

This prevents "churning" — charging at €0.46 to discharge at €0.47 would waste battery cycles for minimal gain.

---

## 🌃 Evening Peak: Discharging When It Counts

### What to Expect

This is when SessyStrategy provides the most value — avoiding expensive grid imports during peak hours.

### Typical Evening Peak Behavior

**6:00 PM - 11:00 PM (Default evening peak: 8:00-10:00 PM)**

The strategy uses **two different mechanisms** during peak hours:

### Mechanism 1: Price Spike Discharge (Priority 1)

**Trigger:** Raw price > `price_discharge` (default 0.39 €/kWh = 0.50 €/kWh import)

**What You Should See:**
```
INFO sessy_strategy: Hour=19  SOC=85%  Raw price=0.46500  Import price=0.57500
INFO sessy_strategy: DISCHARGE override: import price 0.575 > 0.50 — battery setpoint 1500W (SOC 85% → floor 20% over 2.00h)
```

- **Status Sensor:** `discharge`
- **Strategy Select:** `api` (battery setpoint mode)
- **Battery Setpoint:** Positive value (discharge)
- **SOC:** Will gradually decrease

**Why This is Priority #1:**
Avoiding expensive grid imports is the highest-value action. Even with round-trip losses, discharging stored energy at €0.575/kWh import price saves significantly compared to importing.

### Mechanism 2: Evening Peak Excess Discharge (Priority 4)

**Trigger:** 
- Within `evening_peak_start` to `evening_peak_end` (default 8:00-10:00 PM)
- SOC > `soc_target` (you have excess stored energy)
- No remaining hours today exceed `price_discharge` (no more spikes to save for)

**What You Should See:**
```
INFO sessy_strategy: Hour=20  SOC=82%  Raw price=0.18900  Import price=0.29900
INFO sessy_strategy: EVENING PEAK EXCESS: SOC 82% > target 70% — grid export setpoint -350W (spread over 2.00h remaining peak window)
```

- **Status Sensor:** `evening_peak_excess`
- **Strategy Select:** `nom` (grid setpoint mode)
- **Grid Target:** Negative value (export)
- **Behavior:** Battery covers household load + export target simultaneously

### Key Differences

| Aspect | Price Spike | Evening Peak Excess |
|--------|-------------|---------------------|
| **Setpoint Type** | Battery (`api`) | Grid (`nom`) |
| **Goal** | Avoid expensive import | Sell surplus energy |
| **Trigger** | High price > threshold | SOC > target |
| **Strategy** | Discharge toward floor | Export surplus |

---

## 🌙 Night: Cheap Price Charging

### What to Expect

During nighttime hours, prices often drop, and you might see the strategy charge the battery.

### Typical Night Behavior

**12:00 AM - 6:00 AM:**

### Mechanism: Cheap/Negative Price Charge (Priority 2)

**Trigger:** Raw price < `price_charge` (default -0.10 €/kWh)

**What You Should See:**
```
INFO sessy_strategy: Hour=03  SOC=45%  Raw price=-0.15678  Import price=-0.04678
INFO sessy_strategy: CHEAP CHARGE: raw price -0.15678 < -0.10 — battery setpoint -2200W (SOC 45% → 100% over 3.00h cheap window)
```

- **Status Sensor:** `cheap_charge`
- **Strategy Select:** `api` (battery setpoint mode)
- **Battery Setpoint:** Negative value (charge at max power)
- **SOC:** Will rise toward `cheap_soc_target` (default 100%)

### Special Case: SOC Already Full

```
INFO sessy_strategy: Hour=03  SOC=100%  Raw price=-0.15678  Import price=-0.04678
INFO sessy_strategy: CHEAP CHARGE: SOC 100% already at ceiling 100% — holding grid setpoint 0W
```

- **Status Sensor:** `cheap_charge_full`
- **Behavior:** Holds at 0W since battery is already full

### Why This Matters

Charging during cheap/negative price periods:
- **Winter:** Essential for filling the battery when solar is insufficient
- **Summer:** Less common, but captures value when prices go negative
- **Economics:** Every kWh charged at -€0.15 saves €0.15 + €0.11 (surcharge) = €0.26 per kWh used later

---

## 📊 Real-World First Day Example

### Scenario: Sunny Summer Day

| Time | SOC | Raw Price | Strategy | What Happened |
|------|-----|-----------|----------|---------------|
| 06:00 | 35% | €0.08 | DEFAULT | Solar starting, grid 0W |
| 09:00 | 45% | €0.12 | DEFAULT | Solar charging battery |
| 12:00 | 78% | €0.10 | DEFAULT | Battery nearly full |
| 15:00 | 92% | €0.09 | DEFAULT | Battery full, excess solar exported |
| 16:00 | 92% | €0.11 | prepeak_full | Already at target, no charge needed |
| 17:00 | 92% | €0.12 | DEFAULT | Pre-peak ended, waiting |
| 19:00 | 92% | €0.25 | DEFAULT | Price not high enough |
| 20:00 | 88% | €0.35 | DEFAULT | Still below discharge threshold |
| 21:00 | 82% | €0.48 | **discharge** | Price spike! Discharging |
| 22:00 | 75% | €0.52 | **discharge** | Continued spike, discharging |
| 23:00 | 68% | €0.22 | DEFAULT | Spike over, back to default |

### Total Savings
- Avoided importing ~1.4 kWh at €0.52/kWh = €0.73 saved
- Battery ended at 68% SOC, ready for tomorrow

### Scenario: Cloudy Winter Day

| Time | SOC | Raw Price | Strategy | What Happened |
|------|-----|-----------|----------|---------------|
| 00:00 | 45% | €-0.05 | cheap_charge | Charging at max rate |
| 02:00 | 85% | €-0.12 | cheap_charge | Still charging |
| 04:00 | 100% | €0.05 | cheap_charge_full | Battery full |
| 08:00 | 95% | €0.45 | **discharge** | Morning price spike |
| 10:00 | 78% | €0.25 | DEFAULT | Price dropped |
| 14:00 | 62% | €0.18 | DEFAULT | Solar charging |
| 15:00 | 68% | €0.19 | prepeak_charge | Topping up for evening |
| 16:00 | 75% | €0.22 | prepeak_charge | Still charging |
| 18:00 | 80% | €0.42 | **discharge** | Evening spike, discharging |
| 20:00 | 65% | €0.68 | **discharge** | Major spike, discharging hard |
| 22:00 | 52% | €0.45 | **discharge** | Spike continues |
| 23:00 | 40% | €0.15 | DEFAULT | Spike over |

### Total Savings
- Charged 55% at negative/cheap prices = ~2.75 kWh
- Avoided importing ~3.8 kWh at high prices
- Net savings: ~€2.00+ depending on exact prices

---

## 🔍 How to Monitor Your First Day

### Method 1: Status Sensor Attributes

The `sensor.sessy_strategy_status` contains all the information you need:

```yaml
# Example attributes
active_branch: "default"
soc: 68.5
raw_price: 0.23456
import_price: 0.34456
soc_target: 70
soc_floor: 20
price_discharge: 0.39
price_charge: -0.10
active_season: "summer"
min_price_hour: 3
min_price_value: -0.123
```

### Method 2: AppDaemon Logs

Watch the logs in real-time:
```
INFO sessy_strategy: Hour=14  SOC=68%  Raw price=0.23456  Import price=0.34456
INFO sessy_strategy: DEFAULT: grid setpoint 0W — absorb solar, block export
```

### Method 3: Entity History

Use Home Assistant's **History** panel to see:
- SOC sensor over time
- Strategy status changes
- Setpoint values
- Energy prices

---

## 🎯 Checking Status

### Quick Health Check

1. **Is the strategy running?**
   - Check AppDaemon logs for recent entries (every 5 minutes)
   - Verify `sensor.sessy_strategy_status` exists

2. **Are entities being read?**
   - SOC sensor shows reasonable values (0-100%)
   - Price sensor shows current price

3. **Are decisions being made?**
   - Status changes between different branches
   - Setpoints change based on conditions

4. **Are setpoints being applied?**
   - Strategy select switches between "nom" and "api"
   - Grid target and battery setpoint show appropriate values

### Common First-Day Questions

**Q: Why is it always in DEFAULT mode?**
- This is normal if prices are moderate
- DEFAULT is the most common state — it means the strategy sees no reason to override
- This is good! It means your battery is efficiently handling solar

**Q: Why didn't it charge during cheap hours?**
- Check if current price < `price_charge` threshold
- Check if SOC < `cheap_soc_target`
- Check if price sensor is working correctly

**Q: Why didn't it discharge during high prices?**
- Check if current price > `price_discharge` threshold
- Check if SOC > `soc_floor`
- Verify the price sensor is showing raw (not import) prices

**Q: The battery is at 100% but not discharging?**
- This is normal if prices aren't high enough
- The strategy waits for the optimal moment to discharge
- It will eventually discharge as SOC naturally drops or when prices spike

---

## ✅ First Day Checklist

- [ ] AppDaemon is running without errors
- [ ] SessyStrategy logs show regular updates (every 5 minutes)
- [ ] `sensor.sessy_strategy_status` exists and shows data
- [ ] SOC sensor is updating and shows reasonable values
- [ ] Price sensor is updating and shows current prices
- [ ] Strategy has switched between at least 2 different branches
- [ ] Setpoint entities (grid/battery) show non-zero values at times
- [ ] You understand why each strategy decision was made

---

## 🎉 Success!

You've successfully observed SessyStrategy through its first day of operation! You should now have a good understanding of how it behaves and what to expect.

### What You've Learned

- The strategy runs continuously, making decisions every 5 minutes
- It uses a priority chain to determine the best action
- DEFAULT mode (grid 0W) is normal and efficient for most of the day
- It aggressively charges during cheap prices and discharges during expensive prices
- The pre-peak window helps prepare for evening demand
- All decisions are based on real-time data and configurable thresholds

### Next Steps

- **[Create a Dashboard](../tutorials/dashboard-setup.md)** — Set up visual monitoring to easily track strategy behavior
- **[Tune Price Thresholds](../how-to/tune-price-thresholds.md)** — Adjust thresholds for your specific energy costs
- **[Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)** — Set up optimal winter/summer behavior
- **[Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)** — Control thresholds from your dashboard
- **[Understand the Priority Chain](../explanation/strategy-priority-chain.md)** — Deep dive into decision logic

### Pro Tips

1. **Start with defaults:** The default thresholds work well for most Netherlands users
2. **Monitor for a week:** Observe patterns before making adjustments
3. **Check price basis:** Remember thresholds use raw prices, not import prices
4. **Seasonal adjustment:** Consider seasonal overrides for winter vs summer behavior

---

## 📝 Feedback

Found an issue or have suggestions for this tutorial? [Open an issue](https://github.com/your-repo/issues) or contribute improvements via pull request.

---

*Last updated: 2026-08-01*
*Tutorial created: 2026-08-01*