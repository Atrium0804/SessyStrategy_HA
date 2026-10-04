cd

# Required Updates for New Boiler Strategies

## 📋 Update Checklist

To use the new boiler strategies, you need to make the following updates:

### 1. ✅ **apps.yaml** - Already Updated

- Added `market_price_threshold: 0.1` configuration
- Added `cheapest_hours_count: 1` configuration
- Added `current_price_sensor` and `current_price_attribute` entities
- Updated mode_select comment to include new strategy options

### 2. ⚠️ **Home Assistant Configuration** - Manual Update Required

#### Update your `input_select.boiler_strategy_mode` in `configuration.yaml`:

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
      - market_price_threshold      # NEW
      - cheapest_hours              # NEW
    initial: economic
    icon: mdi:thermostat
```

### 3. ⚠️ **Current Price Sensor** - Manual Setup Required

The market price threshold strategy requires a current price sensor.
You have several options:

#### Option A: Use existing Sessy current price

```yaml
# If Sessy provides a current price sensor
current_price_sensor: sensor.sessy_dnhh_current_energy_price
current_price_attribute: price
```

#### Option B: Create a template sensor

```yaml
# In configuration.yaml or a package
template:
  - sensor:
      - name: "Current Energy Price"
        unit_of_measurement: "€/kWh"
        state: >
          {{ state_attr('sensor.sessy_dnhh_energy_price', 'current_price') | float }}
```

#### Option C: Use a utility meter or other price source

```yaml
current_price_sensor: sensor.your_current_price_entity
current_price_attribute: ""  # Leave empty if the sensor directly provides the price
```

### 4. ⚠️ **Configuration Parameters** - Customize as Needed

#### Market Price Threshold

- **Purpose**: Sets the price threshold for switching to heat pump
- **Default**: 0.1 €/kWh
- **Recommended**: Set based on your gas vs electricity price ratio
- **Example**: If gas costs ~0.08 €/kWh and electricity efficiency is 3:1, set threshold to ~0.24 €/kWh

```yaml
market_price_threshold: 0.24  # Example for 3:1 heat pump efficiency
```

#### Cheapest Hours Count

- **Purpose**: Number of cheapest hours to run heat pump
- **Default**: 1 hour
- **Recommended**: 2-6 hours depending on your hot water usage
- **Example**: For a family of 4, 3-4 hours might be optimal

```yaml
cheapest_hours_count: 3  # Use heat pump during 3 cheapest hours
```

### 5. ✅ **Restart Required**

- Restart AppDaemon after making these changes
- The new strategies will be available in your input_select

---

## 🎯 Quick Start Guide

### For Market Price Threshold Strategy:

1. Set up current price sensor (see above)
2. Configure threshold in apps.yaml
3. Select `market_price_threshold` in your strategy mode
4. The boiler will switch to heat pump whenever price ≤ threshold

### For Cheapest Hours Strategy:

1. Ensure your price forecast sensor provides full day data
2. Set the number of cheapest hours in apps.yaml
3. Select `cheapest_hours` in your strategy mode
4. The boiler will switch to heat pump only during the N cheapest hours

---

## 🔍 Verification Steps

1. **Check Apps.yaml** - Confirm new parameters are present
2. **Check Input Select** - Verify new options appear in Home Assistant
3. **Check Current Price Sensor** - Ensure it shows valid price data
4. **Test Strategies** - Switch modes and monitor status sensor
5. **Check Logs** - Look for any errors in AppDaemon logs

---

## 📊 Status Sensor Information

The `sensor.boiler_strategy_status` provides detailed information about the current operation:

- **All Strategies**: temp, mode, days_since_legionella_ok
- **Economic**: avg_price_day, avg_price_night, cheapest_period, in_cheapest_window
- **Market Price**: current_price, threshold
- **Cheapest Hours**: cheapest_hours, cheapest_hours_count, in_cheapest_window

Use this for debugging and creating informative dashboards.

---

## 🚨 Troubleshooting

### Strategy Not Available in Input Select

- **Solution**: Restart Home Assistant to reload the input_select configuration

### Market Price Strategy Not Working

- **Check**: Current price sensor exists and returns numeric values
- **Check**: `current_price_sensor` and `current_price_attribute` are correctly configured
- **Check**: Price is numeric (not string) and within expected range

### Cheapest Hours Strategy Not Working

- **Check**: Price forecast sensor provides full day data (24+ hours)
- **Check**: `cheapest_hours_count` is set to a reasonable value (1-24)
- **Check**: Status sensor shows the identified cheapest hours

### Heat Pump Not Switching On

- **Check**: You're not in legionella boost period
- **Check**: Current price is below threshold (market price strategy)
- **Check**: Current hour is in cheapest hours list (cheapest hours strategy)
- **Check**: Boiler mode select entity is working correctly
