# Boiler Strategy - Multiple Heating Strategies

This updated version of the Boiler Strategy AppDaemon app supports multiple heating strategies for optimizing when to use your heat pump vs gas boiler based on energy prices.

## Available Strategies

### 1. Market Price Threshold - `market_price_threshold`

**How it works:**
- Reads the current local hour's price from the shared price data (`price_forecast_sensor`, same reader as the battery: `cheapest_hours.price_at`)
- Switches to heat pump when price is at or below a configurable threshold
- Default threshold: 0.1 €/kWh
- Uses gas when price is above threshold

**Configuration:**
```yaml
# Price threshold in €/kWh (default: 0.1)
market_price_threshold: 0.1

# Current price sensor (fallback only: used when the shared price data has no price for the current hour)
current_price_sensor: "sensor.current_energy_price"
current_price_attribute: "price"
```

If the sensor state itself contains the price, configure `current_price_attribute: ""` instead. The supplied Home Assistant template sensor and `apps.yaml` use this direct-state form.

**Use case:** Ideal for variable/dynamic energy pricing where you want to heat pump only when electricity is cheap enough.

---

### 2. Cheapest Hours - `cheapest_hours` ⭐ *Default*

**How it works:**
- Ranks the hours of the 24h price window that starts at `cheapest_window_start_h` (default 2 = 02:00 → 02:00)
- Identifies the N cheapest hours in that window — the same window and ranking the battery strategy uses (`cheapest_hours.py`)
- Runs heat pump only during those hours
- Default: 1 cheapest hour

**Configuration:**
```yaml
# Number of cheapest hours to use heat pump (default: 1)
cheapest_hours_count: 3

# Shared with sessy_strategy via the YAML anchor/alias (default: 2)
cheapest_window_start_h: *cheapest_window_start_h

# Price forecast sensor (required for full window analysis)
price_forecast_sensor: "sensor.sessy_dnhh_energy_price"
price_forecast_attribute: "energy_prices"
```

Only N differs between the apps: `cheapest_hours_n` (battery) versus `cheapest_hours_count` (boiler).

**Use case:** Perfect for maximizing savings by concentrating heating during the absolute cheapest times.

---

## Priority Order (All Strategies)

The app evaluates strategies in this priority order:

1. **Legionella Boost** (Highest Priority)
   - If temperature hasn't reached `legionella_temp` in `legionella_boost_days` (default: 7 days)
   - Forces `boost` mode regardless of pricing strategy (unless user explicitly selected `off`)

2. **User Mode Dispatch**
   - Direct modes: `off`, `heatpump`, `hybrid`, `boost`
   - Always takes immediate effect
   - An unset mode or a leftover `economic` (retired) runs as `cheapest_hours`; the app switches the input_select to `cheapest_hours` and logs a WARNING

3. **Legionella Warning**
   - If temperature hasn't reached `legionella_temp` in `legionella_hybrid_days` (default: 6 days)
   - Only for `market_price_threshold` or `cheapest_hours`
   - Forces `hybrid` mode but **only during the cheapest period** for the selected strategy
   - Outside cheapest period, falls through to the pricing strategy

4. **Market Price Threshold**
   - `market_price_threshold`: Use heat pump when price ≤ threshold

5. **Cheapest Hours**
   - `cheapest_hours`: Use heat pump during N cheapest hours of the shared price window

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
  
  # Market price threshold settings
  market_price_threshold: 0.08  # Use heat pump when price ≤ 0.08 €/kWh
  
  # Cheapest hours settings
  cheapest_hours_count: 4  # Use heat pump during 4 cheapest hours
  cheapest_window_start_h: *cheapest_window_start_h  # Same window as sessy_strategy
  
  # Entity IDs
  temp_sensor: "sensor.boiler_temperature"
  price_forecast_sensor: "sensor.sessy_dnhh_energy_price"
  price_forecast_attribute: "energy_prices"
  current_price_sensor: "sensor.current_energy_price"  # Fallback only
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
      - market_price_threshold
      - cheapest_hours
    initial: cheapest_hours
    icon: mdi:thermostat
```

### Required Entities

1. **Temperature Sensor**: Measures boiler temperature
2. **Price Forecast Sensor**: Provides hourly prices in the Sessy format: an `energy_prices` dict with UTC keys, e.g. `'2026-11-09T16:00:00+00:00': 0.60945` (= 17:00 CET). `cheapest_hours.py` converts keys to the AppDaemon local timezone; keys without an offset are read as local. The Frank Energie format (list of `{from, till, price}`) is no longer supported.
3. **Current Price Sensor** (optional): Fallback price for the market price threshold strategy when the price data has no price for the current hour
4. **Boiler Mode Select**: Controls your boiler (off/heatpump/hybrid/boost)
5. **Legionella Tracking**: Input datetime to track when boiler last reached target temp

---

## Status Sensor Attributes

The status sensor (`sensor.boiler_strategy_status`) provides detailed information:

- `active_branch`: Current decision branch (e.g., `cheapest_hours_heatpump`, `market_price_off`)
- `active_branch_label`: Human-readable branch name
- `rule_explanation`: Detailed explanation of the current rule
- `temp`: Current boiler temperature
- `mode`: Current strategy mode
- `days_since_legionella_ok`: Days since last reaching legionella temperature

Strategy-specific attributes:
- **Market Price**: `current_price`, `threshold`
- **Cheapest Hours**: `cheapest_hours`, `cheapest_hours_count`, `in_cheapest_window`, `cheapest_hours_price_threshold`, `cheapest_hours_window_start`, `cheapest_hours_window_end`
- **Legionella Warning**: `cheapest_period`, `in_cheapest_window`

---

## Migration Guide

If you're upgrading from the previous version:

1. **`economic` mode retired** - use `cheapest_hours` (new default) or `market_price_threshold` instead
2. **Remove the `economic_*` keys** from the `boiler_strategy` section in `apps.yaml`
3. **Remove `economic` from the input_select options** and set `initial: cheapest_hours`. A leftover `economic` selection runs as `cheapest_hours`; the app switches the input_select and logs a WARNING
4. **Frank Energie price format dropped** - point `price_forecast_sensor` at the Sessy sensor (`energy_prices`)
5. **Shared window** - the boiler now uses the battery's 24h window (`cheapest_window_start_h`, default 2; it used to default to 23)

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