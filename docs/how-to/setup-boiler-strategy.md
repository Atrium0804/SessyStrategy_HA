# Set Up Boiler Strategy

*Last updated: 2026-11-09 | Part of [How-to Documentation](../index.md)*

---

## Problem / Solution

**Problem:** You have an Ariston hybrid boiler and want to automatically control it based on energy prices while ensuring legionella prevention safety.

**Solution:** Deploy the Boiler Strategy AppDaemon app to intelligently manage your boiler mode, balancing cost optimization with health and safety requirements.

---

## Related Documentation

- [Boiler Strategy Configuration Reference](../reference/configuration/boiler-strategy-config.md)
- [Boiler Strategy Priority Chain](../explanation/boiler-strategy-priority-chain.md)
- [apps.yaml Configuration Reference](../reference/configuration/apps-yaml.md)

---

## Prerequisites

Before you start, ensure you have:

- [x] Home Assistant installed and running
- [x] AppDaemon 4.x installed and configured
- [x] Ariston hybrid boiler integrated with Home Assistant (via Ariston integration or similar)
- [x] A temperature sensor for your boiler water (`sensor.boiler_*`) or equivalent
- [x] The Sessy energy price sensor (e.g., `sensor.sessy_dnhh_energy_price` with an `energy_prices` attribute) — the same sensor the battery strategy uses

---

## Solution Steps

### Step 1: Copy the App File

Copy `files/boiler_strategy.py` to your AppDaemon apps directory, typically:

```
/config/appdaemon/apps/boiler_strategy.py
```

Verify the file is accessible and has the correct permissions.

### Step 2: Create Required Entities in Home Assistant

The app requires several Home Assistant entities. Create these before configuring:

#### Required Input Select
Create an input select for the user mode selection:

1. Go to **Settings → Devices & Services → Helpers**
2. Click **Add Helper** → **Input select**
3. Configure:
   - Name: `Boiler Strategy Mode`
   - Options: `cheapest_hours, market_price_threshold, off, heatpump, hybrid, boost`
   - Initial option: `cheapest_hours`
   - Icon: `mdi:boiler` (optional)
4. Note the entity ID (e.g., `input_select.boiler_strategy_mode`)

#### Required Input Datetime
Create an input datetime for legionella tracking:

1. Go to **Settings → Devices & Services → Helpers**
2. Click **Add Helper** → **Input datetime**
3. Configure:
   - Name: `Boiler Legionella Last OK`
   - Has time: Yes
   - Has date: Yes
   - Icon: `mdi:clock-check` (optional)
4. Note the entity ID (e.g., `input_datetime.boiler_legionella_last_ok`)

The app will automatically update this timestamp whenever the boiler reaches the legionella prevention temperature.

#### Boiler Mode Select
Ensure you have a select entity for controlling the boiler mode. This is typically provided by your boiler integration:

- Entity ID: Usually `select.boiler_mode` or similar
- Options: Should include `off`, `heatpump`, `hybrid`, `boost`, `ariston_app`

If this doesn't exist, check your Ariston integration documentation or create a template select.

### Step 3: Identify Your Entity IDs

Locate the following entities in your Home Assistant:

| Entity Type | Purpose | Example Entity ID | How to Find |
|-------------|---------|-------------------|-------------|
| Temperature sensor | Boiler water temperature | `sensor.boiler_temperature` | Developer Tools → States, filter for `temperature` |
| Price forecast sensor | Energy price forecast (`energy_prices` attribute) | `sensor.sessy_dnhh_energy_price` | Check your Sessy integration |
| Status sensor | App status output | `sensor.boiler_strategy_status` | Will be created by the app |

### Step 4: Configure apps.yaml

Add the boiler strategy configuration to your `apps.yaml` file, typically at `/config/appdaemon/apps/apps.yaml`.

**Minimal configuration with entity mapping:**

```yaml
boiler_strategy:
  module: boiler_strategy
  class: BoilerStrategy

  # REQUIRED: Map to your entities
  temp_sensor: sensor.boiler_temperature
  price_forecast_sensor: sensor.sessy_dnhh_energy_price
  price_forecast_attribute: energy_prices
  mode_select: input_select.boiler_strategy_mode
  boiler_mode_select: select.boiler_mode
  legionella_last_ok_entity: input_datetime.boiler_legionella_last_ok
  status_sensor: sensor.boiler_strategy_status
```

**Full configuration with all options:**

```yaml
boiler_strategy:
  module: boiler_strategy
  class: BoilerStrategy

  # Legionella prevention settings
  legionella_temp: 65             # Target temperature in °C
  legionella_hybrid_days: 6       # Days before hybrid warning
  legionella_boost_days: 7        # Days before boost forced

  # Market price threshold mode
  market_price_threshold: 0.1     # Heat pump runs when price <= this (€/kWh)

  # Cheapest hours mode (default)
  cheapest_hours_count: 1         # N cheapest hours of the price window
  cheapest_window_start_h: *cheapest_window_start_h   # Shared with sessy_strategy (default 2 = 02:00 → 02:00)

  # Delay before re-running after input changes
  rerun_debounce_s: 2.0

  # Entity IDs
  temp_sensor: sensor.boiler_temperature
  price_forecast_sensor: sensor.sessy_dnhh_energy_price
  price_forecast_attribute: energy_prices
  current_price_sensor: sensor.sessy_dnhh_energy_price   # Fallback only
  current_price_attribute: ""
  mode_select: input_select.boiler_strategy_mode
  boiler_mode_select: select.boiler_mode
  legionella_last_ok_entity: input_datetime.boiler_legionella_last_ok
  status_sensor: sensor.boiler_strategy_status
```

!!! note
    `*cheapest_window_start_h` is a YAML alias for the anchor `&cheapest_window_start_h` in the `sessy_strategy` section. The anchor must appear earlier in the same `apps.yaml`. Without the battery section, set a number instead (for example `2`).

### Step 5: Restart AppDaemon

After saving your configuration, restart AppDaemon for the changes to take effect:

```bash
# If using systemd
sudo systemctl restart appdaemon

# Or via the AppDaemon web UI
# Navigate to AppDaemon → System → Restart
```

### Step 6: Verify Installation

Check that the app is running and producing output:

1. **Check AppDaemon logs:**
   ```bash
   tail -f /config/appdaemon/logs/appdaemon.log
   ```
   Look for the message: `Boiler strategy starting up`

2. **Check the status sensor:**
   - In Home Assistant, go to **Developer Tools → States**
   - Look for `sensor.boiler_strategy_status`
   - It should show the current active branch (e.g., `cheapest_hours_off`, `legionella_boost`, etc.)
   - Click on the entity to see all attributes including temperature, mode, and days since last legionella OK

3. **Test the mode select:**
   - Change the `input_select.boiler_strategy_mode` value
   - Verify that `select.boiler_mode` updates accordingly
   - Check the logs for strategy change messages

### Step 7: Initial Legionella Timestamp

On first run, the `legionella_last_ok_entity` will be empty. The app handles this by assuming it's at the hybrid warning threshold (6 days).

To initialize it properly:

1. Wait for the boiler to reach at least 65°C (or your configured `legionella_temp`)
2. The app will automatically stamp the current datetime to `legionella_last_ok_entity`
3. Verify the timestamp is set correctly

Alternatively, you can manually set it:

1. Go to **Developer Tools → Services**
2. Call the `input_datetime.set_datetime` service:
   - Entity: `input_datetime.boiler_legionella_last_ok`
   - Datetime: Current date and time

---

## Common Issues and Fixes

### Issue: App doesn't start, no logs

❌ **Error:** No `Boiler strategy starting up` message in logs

✅ **Fix:**
1. Verify the file exists at `/config/appdaemon/apps/boiler_strategy.py`
2. Check file permissions: `chmod 644 /config/appdaemon/apps/boiler_strategy.py`
3. Verify apps.yaml syntax with a YAML validator
4. Restart AppDaemon and check for syntax errors in logs

### Issue: Boiler mode doesn't change

❌ **Error:** `select.boiler_mode` stays the same regardless of configuration

✅ **Fix:**
1. Verify `boiler_mode_select` entity ID in configuration matches your actual entity
2. Check that the entity exists and is accessible
3. Ensure the user running AppDaemon has permissions to write to the entity
4. Check logs for `Failed to set boiler mode` errors

### Issue: Legionella timestamp never updates

❌ **Error:** `legionella_last_ok_entity` remains at initial value even when boiler is hot

✅ **Fix:**
1. Verify `temp_sensor` is reading correct values
2. Check that the temperature exceeds `legionella_temp` (default 65°C)
3. Verify `legionella_last_ok_entity` entity ID is correct
4. Check logs for `Failed to stamp legionella_last_ok` errors

### Issue: Price mode doesn't consider prices

❌ **Error:** Boiler runs at wrong times, not respecting cheap hours

✅ **Fix:**
1. Verify `price_forecast_sensor` entity ID is correct
2. Check that the sensor has an `energy_prices` (or your configured) attribute
3. Verify it is a dict of ISO timestamps to prices in the Sessy format, e.g. `'2026-11-09T16:00:00+00:00': 0.60945` (UTC keys; 17:00 CET). The list-of-`{from, till, price}` format is no longer supported
4. Check `cheapest_window_start_h` and `cheapest_hours_count` match your intended window and N

!!! tip
    Use **Developer Tools → States** to inspect your price forecast sensor and verify it has the expected structure.

### Issue: Days since last OK always shows 6

❌ **Error:** `days_since_legionella_ok` attribute always reports ~6 days

✅ **Fix:**
1. This is expected behavior if `legionella_last_ok_entity` has never been set
2. The app defaults to `legionella_hybrid_days` (6) when the entity is unset
3. Initialize the timestamp as described in Step 7 above

### Migrating from the `economic` mode

The `economic` mode (day/night window comparison) is retired. To migrate:

1. Use `cheapest_hours` (the default) or `market_price_threshold` instead.
2. Remove all `economic_*` keys (the day and night window start/end hours) from `apps.yaml`.
3. Remove `economic` from the `input_select.boiler_strategy_mode` options and set the initial option to `cheapest_hours`.
4. Use the Sessy price format (`energy_prices` dict). The Frank Energie format (list of `{from, till, price}`) is no longer supported.

!!! note
    Until you remove it, a leftover `economic` selection runs as `cheapest_hours`. The app switches the `input_select` to `cheapest_hours` and logs a WARNING.

---

## Quick Verification Checklist

- [ ] `boiler_strategy.py` copied to AppDaemon apps directory
- [ ] `input_select.boiler_strategy_mode` created with correct options
- [ ] `input_datetime.boiler_legionella_last_ok` created
- [ ] `select.boiler_mode` exists (from boiler integration)
- [ ] `temp_sensor` entity exists and shows temperature
- [ ] `price_forecast_sensor` entity exists and shows prices
- [ ] `apps.yaml` updated with boiler_strategy configuration
- [ ] AppDaemon restarted
- [ ] `Boiler strategy starting up` appears in logs
- [ ] `sensor.boiler_strategy_status` entity exists and updates

---

## See Also

- [Boiler Strategy Configuration Reference](../reference/configuration/boiler-strategy-config.md)
- [Tune Price Thresholds](tune-price-thresholds.md)
- [Debug Strategy Decisions](debug-strategy-decisions.md)
