---
title: Getting Started with SessyStrategy HA
doc_type: tutorial
audience: beginners
prerequisites: 
  - Home Assistant (tested on 2024.6+)
  - AppDaemon (4.x+)
  - Sessy integration installed
  - Dynamic energy price sensor
tags:
  - getting-started
  - beginner
  - installation
created: 2026-08-01
last_updated: 2026-08-01
---

# Getting Started with SessyStrategy HA

**Estimated reading time:** 30-45 minutes | **Difficulty:** Beginner

---

## What You Will Learn

- Install and configure AppDaemon for SessyStrategy
- Set up the SessyStrategy application in your Home Assistant environment
- Configure the basic settings to match your battery system
- Verify the strategy is running correctly
- Monitor your first strategy decisions

## Prerequisites

Before starting this tutorial, ensure you have:

- [x] **Home Assistant** installed and running (tested on 2024.6+)
- [x] **Sessy integration** installed and configured with your battery
- [x] **Dynamic energy price sensor** (e.g., from ha-dsmr, Nordic Energy, or other price integration)
- [x] Basic familiarity with YAML configuration files
- [x] SSH/Samba access or File Editor add-on for Home Assistant

## Related Documentation

- [First Day Operation](first-day-operation.md) — What to expect on your first day
- [Dashboard Setup](dashboard-setup.md) — Create visual monitoring for your strategy

---

## Step 1: Install AppDaemon

### What This Step Does

AppDaemon is a Python-based automation framework that runs alongside Home Assistant. SessyStrategy runs as an AppDaemon application, which allows it to execute complex logic on a schedule and interact with Home Assistant entities.

### How to Do It

1. **Open the Add-on Store:**
   In Home Assistant, go to **Settings → Add-ons → Add-on store**

2. **Find AppDaemon 4:**
   Search for "AppDaemon 4" in the add-on store

3. **Install AppDaemon:**
   Click **Install** and wait for the installation to complete

4. **Configure AppDaemon:**
   After installation, click **Configuration** and set:
   ```yaml
   time_zone: Europe/Amsterdam
   latitude: 52.0
   longitude: 5.1
   elevation: 0
   plugins:
     HASS:
       type: hass
       ha_url: http://homeassistant.local:8123
       token: YOUR_LONG_LIVED_ACCESS_TOKEN
   ```
   > **Note:** Replace the latitude, longitude, and ha_url with your values. For `ha_url`, use your Home Assistant URL.

5. **Generate Access Token:**
   In Home Assistant, go to **Profile → Long-lived access tokens**
   - Click **Create Token**
   - Give it a name like "AppDaemon"
   - Copy the generated token and paste it into the AppDaemon configuration

6. **Enable Startup Options:**
   - Enable **Start on boot**
   - Enable **Watchdog**
   - Enable **Show in sidebar** (optional)

7. **Start AppDaemon:**
   Click **Start** to launch AppDaemon

### Expected Result

- AppDaemon add-on shows "Running" status
- AppDaemon log shows successful connection to Home Assistant
- You can access AppDaemon logs via **Settings → Add-ons → AppDaemon → Log**

### Troubleshooting

**If AppDaemon fails to start:**
- Double-check your long-lived access token is correct
- Verify the ha_url matches your Home Assistant URL
- Check that your time zone is set correctly
- Ensure your Home Assistant and AppDaemon versions are compatible

---

## Step 2: Copy Strategy Files

### What This Step Does

Copy the SessyStrategy application file and sample configuration to your AppDaemon apps directory.

### How to Do It

1. **Locate your AppDaemon apps directory:**
   For the AppDaemon add-on, this is typically:
   ```
   /config/appdaemon/apps/
   ```

2. **Copy the strategy file:**
   Use one of these methods:
   
   **Method A: Using File Editor add-on**
   - Install the "File Editor" add-on if not already installed
   - Open File Editor from the sidebar
   - Navigate to `/config/appdaemon/apps/`
   - Click **New File** and name it `sessy_strategy.py`
   - Copy the contents of `files/sessy_strategy.py` from this repository
   - Save the file

   **Method B: Using SSH/Samba**
   - Use SCP, SFTP, or Samba to copy `files/sessy_strategy.py` to `/config/appdaemon/apps/`
   - Example SCP command:
     ```bash
     scp files/sessy_strategy.py homeassistant@your-ha-ip:/config/appdaemon/apps/
     ```

   **Method C: Using local file system (if running HAOS on same machine)**
   - Copy the file directly to the apps directory

3. **Copy the configuration file:**
   - Copy `files/apps.yaml` to `/config/appdaemon/apps/apps.yaml`
   - Or create a new `apps.yaml` file in the same directory

### Expected Result

- `sessy_strategy.py` exists in `/config/appdaemon/apps/`
- `apps.yaml` exists in `/config/appdaemon/apps/`

### Troubleshooting

**If files don't appear:**
- Check file permissions — Home Assistant needs read access
- Verify the file path is correct
- Check that you're copying to the AppDaemon apps directory, not the root config

---

## Step 3: Configure apps.yaml

### What This Step Does

Configure the SessyStrategy application to match your specific battery system and entity IDs.

### How to Do It

1. **Open the apps.yaml file:**
   Edit `/config/appdaemon/apps/apps.yaml`

2. **Set required entity IDs:**
   Replace the default entity IDs with your own. The defaults use specific suffixes (`alt9`, `dnhh`, `pwkn`) that likely don't match your installation:

   ```yaml
   sessy_strategy:
     module: sessy_strategy
     class: SessyStrategy
     
     # Required entity IDs — UPDATE THESE TO MATCH YOUR SETUP
     strategy_select: select.sessy_battery_alt9_power_strategy
     grid_target: number.sessy_pwkn_grid_target
     battery_setpoint: number.sessy_battery_alt9_power_setpoint
     soc_sensor: sensor.sessy_battery_alt9_state_of_charge
     price_sensor: sensor.sessy_dnhh_energy_price
     status_sensor: sensor.sessy_strategy_status
   ```

   **To find your entity IDs:**
   - Go to **Developer Tools → States** in Home Assistant
   - Look for entities related to your Sessy battery
   - Common patterns:
     - SOC sensor: `sensor.sessy_battery_<id>_state_of_charge`
     - Price sensor: `sensor.sessy_<provider>_energy_price`
     - Strategy select: `select.sessy_battery_<id>_power_strategy`
     - Grid target: `number.sessy_<id>_grid_target`
     - Battery setpoint: `number.sessy_battery_<id>_power_setpoint`

3. **Configure battery specifications (optional):**
   Adjust these to match your battery system:

   ```yaml
   # Battery / hardware
   capacity_wh: 5000          # Your battery capacity in Wh
   max_power_w: 2200          # Your inverter/battery max power in W
   ```

4. **Configure SOC targets (optional):**
   ```yaml
   # State-of-charge targets
   soc_target: 70             # % SOC to reach before evening peak
   soc_floor: 0              # % SOC floor — never discharge below this
   cheap_soc_target: 100      # % SOC ceiling for cheap-price charging
   ```

5. **Configure pricing (optional):**
   ```yaml
   # Pricing
   surcharge: 0.11            # Import surcharge €/kWh (raw export → import)
   price_discharge: 0.39      # Raw price above which to force discharge
   price_charge: -0.10        # Raw price below which to charge from grid
   min_arbitrage_margin: 0.05 # Min €/kWh spread to justify pre-peak charge
   ```

6. **Save the configuration:**
   Save the `apps.yaml` file

### Expected Result

- `apps.yaml` contains valid YAML configuration
- All required entity IDs point to existing entities in your Home Assistant
- Battery specifications match your hardware

### Troubleshooting

**If you're unsure about entity IDs:**
- Check [Entity Reference](../reference/entity-reference.md) for detailed information
- Use **Developer Tools → States** to browse available entities
- Look for entities created by your Sessy integration

**If you get YAML syntax errors:**
- Use a YAML validator to check your syntax
- Ensure proper indentation (2 spaces per level)
- Make sure all colons have a space after them

---

## Step 4: Set Up Optional Components

### What This Step Does

Set up optional components for enhanced functionality: Home Battery integration and live tuning helpers.

### How to Do It

**Option A: Home Battery Integration (Recommended)**

1. **Copy custom component:**
   Copy the Home Battery integration files:
   ```bash
   cp -r files/custom_components/home_battery/ /config/custom_components/home_battery/
   ```

2. **Restart Home Assistant:**
   Restart Home Assistant to load the new integration

3. **Add the integration:**
   - Go to **Settings → Devices & Services**
   - Click **Add Integration**
   - Search for "Home Battery" and add it
   - This creates the mode selector and tuning helpers automatically

**Option B: Manual Helper Setup**

If you prefer not to use the Home Battery integration, you can create the helpers manually:

1. **Create mode selector:**
   Add to your `configuration.yaml`:
   ```yaml
   input_select:
     sessy_season_mode:
       name: "Sessy Season Mode"
       options:
         - auto
         - summer
         - winter
       initial: auto
       icon: mdi:calendar-season
   ```

2. **Create tuning helpers:**
   ```yaml
   input_number:
     home_battery_soc_target:
       name: "SOC Target"
       min: 0
       max: 100
       step: 1
       unit_of_measurement: "%"
       icon: mdi:battery-90
       
     home_battery_soc_floor:
       name: "SOC Floor"
       min: 0
       max: 100
       step: 1
       unit_of_measurement: "%"
       icon: mdi:battery-20
       
     home_battery_price_discharge:
       name: "Price Discharge Threshold"
       min: -1
       max: 2
       step: 0.01
       unit_of_measurement: "€/kWh"
       icon: mdi:currency-eur
       
     home_battery_price_charge:
       name: "Price Charge Threshold"
       min: -2
       max: 1
       step: 0.01
       unit_of_measurement: "€/kWh"
       icon: mdi:currency-eur
   ```

3. **Update apps.yaml:**
   Add references to your helpers:
   ```yaml
   mode_select: select.home_battery_mode
   setpoint_entity: number.home_battery_setpoint
   season_mode_entity: input_select.sessy_season_mode
   soc_target_entity: number.home_battery_soc_target
   soc_floor_entity: number.home_battery_soc_floor
   price_discharge_entity: number.home_battery_price_discharge
   price_charge_entity: number.home_battery_price_charge
   min_arbitrage_margin_entity: number.home_battery_min_arbitrage_margin
   ```

### Expected Result

- Home Battery integration is installed (if using Option A)
- Helper entities exist in Home Assistant (if using Option B)
- `apps.yaml` references the correct entity IDs

### Troubleshooting

**If Home Battery integration doesn't appear:**
- Check that files were copied to the correct location
- Verify file permissions
- Restart Home Assistant and check logs for errors

---

## Step 5: Verify AppDaemon Configuration

### What This Step Does

Ensure your AppDaemon installation is properly configured to run SessyStrategy.

### How to Do It

1. **Check appdaemon.yaml:**
   Verify that `/config/appdaemon/appdaemon.yaml` exists and is properly configured:
   ```yaml
   appdaemon:
     time_zone: Europe/Amsterdam
     latitude: 52.0
     longitude: 5.1
     elevation: 0
     plugins:
       HASS:
         type: hass
         ha_url: http://homeassistant.local:8123
         token: YOUR_LONG_LIVED_ACCESS_TOKEN
   ```

2. **Check directory structure:**
   Your AppDaemon directory should look like:
   ```
   /config/appdaemon/
   ├── appdaemon.yaml
   └── apps/
       ├── apps.yaml
       └── sessy_strategy.py
   ```

3. **Verify file permissions:**
   Ensure Home Assistant has read access to all files

### Expected Result

- AppDaemon configuration file exists and is valid
- Directory structure is correct
- All files are readable by Home Assistant

---

## Step 6: Restart AppDaemon

### What This Step Does

Restart AppDaemon to load the new SessyStrategy application.

### How to Do It

1. **Restart AppDaemon:**
   - Go to **Settings → Add-ons → AppDaemon**
   - Click **Restart**

2. **Wait for startup:**
   AppDaemon should start within a few seconds

3. **Check logs:**
   - Go to **Settings → Add-ons → AppDaemon → Log**
   - Look for the startup message:
     ```
     INFO sessy_strategy: Sessy strategy starting up
     ```

### Expected Result

- AppDaemon restarts successfully
- SessyStrategy logs show successful initialization
- No errors in the AppDaemon log

### Troubleshooting

**If SessyStrategy doesn't start:**
- Check that `sessy_strategy.py` is in the correct directory
- Verify YAML syntax in `apps.yaml`
- Ensure all referenced entities exist in Home Assistant
- Check that AppDaemon has proper permissions

**If you see entity not found errors:**
- Double-check all entity IDs in `apps.yaml`
- Verify entities exist in **Developer Tools → States**
- Update entity IDs if they're incorrect

---

## Step 7: Verify Entities

### What This Step Does

Confirm that SessyStrategy has created the status sensor and is writing to the correct entities.

### How to Do It

1. **Check status sensor:**
   - Go to **Developer Tools → States**
   - Look for `sensor.sessy_strategy_status` (or your configured status_sensor)
   - The sensor should show a state like "default", "discharge", "cheap_charge", etc.

2. **Check strategy select entity:**
   - Look for your `strategy_select` entity
   - It should switch between "nom" and "api" as the strategy changes

3. **Check setpoint entities:**
   - Look for your `grid_target` and `battery_setpoint` entities
   - They should show appropriate values based on the current strategy

4. **Check SOC and price sensors:**
   - Verify your `soc_sensor` shows current battery SOC
   - Verify your `price_sensor` shows current energy price

### Expected Result

- `sensor.sessy_strategy_status` exists and shows current strategy state
- Strategy select entity switches between "nom" and "api"
- Setpoint entities show appropriate values
- SOC and price sensors show current data

### Troubleshooting

**If status sensor doesn't exist:**
- Check that `status_sensor` is configured in `apps.yaml`
- Verify the entity doesn't already exist with a different name
- Check AppDaemon logs for errors

**If setpoint entities don't change:**
- Verify entity IDs are correct in `apps.yaml`
- Check that entities exist and are writable
- Look for errors in AppDaemon logs

---

## Step 8: First Run and Monitoring

### What This Step Does

Monitor SessyStrategy during its first few cycles to ensure it's working correctly.

### How to Do It

1. **Watch the logs:**
   - Open **Settings → Add-ons → AppDaemon → Log**
   - You should see output like:
     ```
     INFO sessy_strategy: Hour=14  SOC=72%  Raw price=0.02590  Import price=0.13590
     INFO sessy_strategy: DEFAULT: grid setpoint 0W — absorb solar, block export
     ```

2. **Observe strategy decisions:**
   - The strategy runs every 5 minutes
   - Watch how it responds to price changes and SOC levels
   - Common branches you'll see:
     - `DEFAULT`: Normal operation, grid setpoint 0W
     - `discharge`: Price spike discharge
     - `cheap_charge`: Charging during cheap price periods
     - `prepeak_charge`: Pre-peak charging window
     - `evening_peak_excess`: Evening peak excess discharge

3. **Check status sensor attributes:**
   - View the attributes of `sensor.sessy_strategy_status`
   - Look for attributes like:
     - `active_branch`: Current active strategy branch
     - `soc`: Current SOC
     - `raw_price`: Current raw price
     - `import_price`: Current import price
     - `soc_target`: Target SOC
     - `price_discharge`: Discharge threshold
     - `price_charge`: Charge threshold

### Expected Result

- AppDaemon logs show regular strategy updates
- Status sensor shows current strategy state and attributes
- Setpoint entities change based on strategy decisions
- No errors in the logs

### Troubleshooting

**If no log output appears:**
- Check that AppDaemon is running
- Verify SessyStrategy is properly configured in `apps.yaml`
- Ensure critical entities (SOC sensor, price sensor) exist

**If strategy always shows DEFAULT:**
- This is normal during periods of moderate pricing
- Check your price thresholds in `apps.yaml`
- Verify current price is within expected range

---

## Verification

To confirm everything is working correctly:

1. [x] AppDaemon is running and shows no errors in the log
2. [x] SessyStrategy logs show successful startup and regular updates
3. [x] `sensor.sessy_strategy_status` exists and shows current state
4. [x] Strategy select entity switches between "nom" and "api"
5. [x] Setpoint entities show appropriate values
6. [x] SOC and price sensors show current data
7. [x] Strategy responds to price changes and SOC levels

---

## Success

[!note]
You have successfully installed and configured SessyStrategy HA! Your battery is now making intelligent decisions based on real-time energy prices.

### Next Steps

Now that you're up and running, consider:

- **[Tune Price Thresholds](../how-to/tune-price-thresholds.md)** — Adjust charge/discharge prices for your specific situation and energy costs
- **[Set Up Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)** — Add dashboard controls to adjust settings without restarting AppDaemon
- **[Create a Dashboard](../tutorials/dashboard-setup.md)** — Set up visual monitoring for your battery strategy
- **[Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)** — Set up winter/summer behavior for optimal year-round performance
- **[Understand the Priority Chain](../explanation/strategy-priority-chain.md)** — Learn how strategy decisions are made

### Learn More

- **[Strategy Priority Chain](../explanation/strategy-priority-chain.md)** — Deep dive into how decisions are made
- **[Price Basis: Raw vs Import](../explanation/price-basis-raw-vs-import.md)** — Understand price calculations
- **[Setpoint Types Explained](../explanation/setpoint-types-explained.md)** — Learn about battery vs grid setpoints

---

## Feedback

Found an issue or have suggestions for this tutorial? [Open an issue](https://github.com/your-repo/issues) or contribute improvements via pull request.

---

*Last updated: 2026-08-01*
*Tutorial created: 2026-08-01*