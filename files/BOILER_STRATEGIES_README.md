# Boiler Strategy - Multiple Heating Strategies

This updated version of the Boiler Strategy AppDaemon app supports multiple heating strategies for optimizing when to use your heat pump vs gas boiler based on energy prices.

## Available Strategies

### 1. Economic (Day/Night Window) - `economic` ⭐ *Default*

**How it works:**
- Compares the average forecast price between two configurable time windows (day vs night)
- Runs the heat pump only during the cheaper period
- Falls back to gas outside the cheaper period

**Configuration:**
```yaml
# Day period (default: 10:00-16:00)
economic_day_start: 10
economic_day_end: 16

# Night period (default: 00:00-06:00)
economic_night_start: 0
economic_night_end: 6
```

**Use case:** Good for fixed tariff plans with known cheap/expensive periods.

---

### 2. Market Price Threshold - `market_price_threshold`

**How it works:**
- Monitors the current market price
- Switches to heat pump when price drops below a configurable threshold
- Default threshold: 0.1 €/kWh
- Uses gas when price is above threshold

**Configuration:**
```yaml
# Price threshold in €/kWh (default: 0.1)
market_price_threshold: 0.1

# Current price sensor (required)
current_price_sensor: "sensor.current_energy_price"
current_price_attribute: "price"
```

If the sensor state itself contains the price, configure `current_price_attribute: ""` instead. The supplied Home Assistant template sensor and `apps.yaml` use this direct-state form.

**Use case:** Ideal for variable/dynamic energy pricing where you want to heat pump only when electricity is cheap enough.

---

### 3. Cheapest Hours - `cheapest_hours`

**How it works:**
- Analyzes the full day's price forecast
- Identifies the N cheapest hours in the calendar day
- Runs heat pump only during those hours
- Default: 1 cheapest hour

**Configuration:**
```yaml
# Number of cheapest hours to use heat pump (default: 1)
cheapest_hours_count: 3

# Price forecast sensor (required for full day analysis)
price_forecast_sensor: "sensor.sessy_dnhh_energy_price"
price_forecast_attribute: "energy_prices"
```

**Use case:** Perfect for maximizing savings by concentrating heating during the absolute cheapest times.

---

## Priority Order (All Strategies)

The app evaluates strategies in this priority order:

1. **Legionella Boost** (Highest Priority)
   - If temperature hasn't reached `legionella_temp` in `legionella_boost_days` (default: 7 days)
   - Forces `boost` mode regardless of pricing strategy (unless user explicitly selected `off`)

2. **User Mode Override**
   - Direct modes: `off`, `heatpump`, `hybrid`, `boost`
   - Always takes immediate effect

3. **Legionella Warning**
   - If temperature hasn't reached `legionella_temp` in `legionella_hybrid_days` (default: 6 days)
   - Forces `hybrid` mode but **only during the cheapest period** for the selected strategy
   - Outside cheapest period, falls through to the pricing strategy

4. **Strategy-Specific Logic**
   - `economic`: Use heat pump during cheaper day/night window
   - `market_price_threshold`: Use heat pump when price < threshold
   - `cheapest_hours`: Use heat pump during N cheapest hours

---

## Configuration Example

```yaml
# In apps.yaml
boiler_strategy:
  module: boiler_strategy
  class: BoilerStrategy
  
  # Legionella settings
  legionella_temp: 65
  legionella_hybrid_days: 6
  legionella_boost_days: 7
  
  # Economic strategy settings
  economic_day_start: 10
  economic_day_end: 16
  economic_night_start: 0
  economic_night_end: 6
  
  # Market price threshold settings
  market_price_threshold: 0.08  # Use heat pump when price ≤ 0.08 €/kWh
  
  # Cheapest hours settings
  cheapest_hours_count: 4  # Use heat pump during 4 cheapest hours
  
  # Entity IDs
  temp_sensor: "sensor.boiler_temperature"
  price_forecast_sensor: "sensor.energy_price_forecast"
  price_forecast_attribute: "prices"
  current_price_sensor: "sensor.current_energy_price"
  current_price_attribute: "price"
  mode_select: "input_select.boiler_strategy_mode"
  boiler_mode_select: "select.boiler_mode"
  legionella_last_ok_entity: "input_datetime.boiler_legionella_last_ok"
  status_sensor: "sensor.boiler_strategy_status"
  
  # Debounce
  rerun_debounce_s: 2.0
```

---

## Home Assistant Setup

### Required Input Select

Add this to your `configuration.yaml`:

```yaml
input_select:
  boiler_strategy_mode:
    name: "Boiler Strategy Mode"
    options:
      - off
      - heatpump
      - hybrid
      - boost
      - economic
      - market_price_threshold
      - cheapest_hours
    initial: economic
    icon: mdi:thermostat
```

### Required Entities

1. **Temperature Sensor**: Measures boiler temperature
2. **Price Forecast Sensor**: Provides hourly price forecasts (Sessy or FrankEnergy format)
3. **Current Price Sensor**: Provides real-time price (for market price threshold strategy)
4. **Boiler Mode Select**: Controls your boiler (off/heatpump/hybrid/boost)
5. **Legionella Tracking**: Input datetime to track when boiler last reached target temp

---

## Status Sensor Attributes

The status sensor (`sensor.boiler_strategy_status`) provides detailed information:

- `active_branch`: Current decision branch (e.g., `economic_heatpump`, `market_price_off`)
- `active_branch_label`: Human-readable branch name
- `rule_explanation`: Detailed explanation of the current rule
- `temp`: Current boiler temperature
- `mode`: Current strategy mode
- `days_since_legionella_ok`: Days since last reaching legionella temperature

Strategy-specific attributes:
- **Economic**: `avg_price_day`, `avg_price_night`, `cheapest_period`, `in_cheapest_window`
- **Market Price**: `current_price`, `threshold`
- **Cheapest Hours**: `cheapest_hours`, `cheapest_hours_count`, `in_cheapest_window`

---

## Migration Guide

If you're upgrading from the previous version:

1. **No breaking changes** - existing `economic` strategy works exactly as before
2. **New strategies available** - add the new configuration options to enable them
3. **New entity required** - add `current_price_sensor` for market price threshold strategy
4. **Mode options extended** - add new options to your input_select if you want to use the new strategies

---

## Troubleshooting

### Prices Not Updating
- Check that your price sensors are working correctly
- Verify the attribute names match your configuration
- Ensure prices are in numeric format (not strings)

### Strategy Not Changing
- Check that the mode_select entity has the correct value
- Verify the strategy name is spelled correctly (case-sensitive: `market_price_threshold`, `cheapest_hours`)
- Look at the status sensor attributes for debugging information

### Heat Pump Not Turning On
- Check if you're in a legionella warning/boost period
- Verify the current price is below your threshold (for market price strategy)
- Check if current hour is in the cheapest hours list (for cheapest hours strategy)

---

## Performance Notes

- The app runs every 15 minutes by default
- Price data is read fresh each cycle
- Input changes trigger a debounced re-run (2 seconds by default)
- All calculations are optimized for minimal processing

---

## Support

For issues or questions:
1. Check the Home Assistant logs for error messages
2. Verify all entity IDs exist and are accessible
3. Check the status sensor attributes for clues about the current decision