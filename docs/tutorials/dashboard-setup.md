---
title: Dashboard Setup with ApexCharts for SessyStrategy HA
doc_type: tutorial
audience: intermediate
prerequisites: 
  - SessyStrategy successfully installed and running
  - ApexCharts card installed in Home Assistant
  - Basic Lovelace dashboard experience
tags:
  - dashboard
  - visualization
  - apexcharts
  - intermediate
created: 2026-08-01
last_updated: 2026-08-01
---

# Dashboard Setup with ApexCharts for SessyStrategy HA

**Estimated reading time:** 20-30 minutes | **Difficulty:** Intermediate

---

## What You Will Learn

- Install and configure the ApexCharts card for Home Assistant
- Create a status card to monitor current strategy state
- Build price and SOC charts to visualize energy patterns
- Create setpoint charts to track strategy decisions
- Combine all elements into a comprehensive battery strategy dashboard
- Add advanced features like thresholds and branch indicators

## Prerequisites

Before starting this tutorial, ensure you have:

- [x] **SessyStrategy installed** — Completed [Getting Started Tutorial](getting-started.md)
- [x] **SessyStrategy running** — Strategy making decisions and updating entities
- [x] **Basic dashboard** — Familiarity with Lovelace dashboard editor
- [x] **HACS installed** — For easy ApexCharts card installation (recommended)

## Related Documentation

- [Getting Started](getting-started.md) — Installation and setup guide
- [First Day Operation](first-day-operation.md) — Understand strategy behavior

---

## Step 1: Install ApexCharts Card

### What This Step Does

ApexCharts is a powerful charting library for Home Assistant that provides beautiful, interactive charts perfect for visualizing battery and price data.

### How to Do It

**Method A: Using HACS (Recommended)**

1. **Open HACS:**
   - Go to **Settings → Add-ons → HACS**
   - Or click HACS in the sidebar

2. **Find ApexCharts Card:**
   - Go to **Frontend** tab
   - Search for "ApexCharts Card"

3. **Install the Card:**
   - Click **Install**
   - Wait for installation to complete

4. **Restart Home Assistant:**
   - Restart Home Assistant to load the new card

**Method B: Manual Installation**

1. **Download the card:**
   - Go to [https://github.com/RomRider/apexcharts-card](https://github.com/RomRider/apexcharts-card)
   - Download the latest release

2. **Copy to Home Assistant:**
   ```bash
   # Copy the apexcharts-card directory to your www directory
   cp -r apexcharts-card/ /config/www/apexcharts-card/
   ```

3. **Add resource:**
   Add to your `configuration.yaml`:
   ```yaml
   frontend:
     extra_module_url:
       - /local/apexcharts-card.js
   ```
   Or add via **Settings → Dashboards → Resources → Add Resource**:
   - URL: `/local/apexcharts-card.js`
   - Resource type: JavaScript Module

4. **Restart Home Assistant:**

### Expected Result

- ApexCharts card is available in Lovelace card picker
- You can add ApexCharts cards to your dashboard

### Troubleshooting

**If ApexCharts doesn't appear in card picker:**
- Verify HACS installed correctly
- Check that Home Assistant restarted properly
- Ensure you're using a compatible Home Assistant version (2023.6+)
- Check browser console for errors (F12 → Console)

---

## Step 2: Create Status Card

### What This Step Does

Create a simple status card to show the current strategy state and key information at a glance.

### How to Do It

1. **Open your dashboard:**
   - Go to the dashboard where you want to add the card
   - Click **Edit Dashboard** (pencil icon)

2. **Add a Markdown card for title:**
   ```yaml
   type: markdown
   content: "# 🔋 SessyStrategy HA Dashboard"
   ```

3. **Add an Entities card for status overview:**
   ```yaml
   type: entities
   title: Strategy Status
   entities:
     - sensor.sessy_strategy_status
     - entity: select.sessy_battery_alt9_power_strategy
       name: Strategy Mode
     - entity: number.sessy_battery_alt9_power_setpoint
       name: Battery Setpoint
     - entity: number.sessy_pwkn_grid_target
       name: Grid Target
     - entity: sensor.sessy_battery_alt9_state_of_charge
       name: Battery SOC
     - entity: sensor.sessy_dnhh_energy_price
       name: Energy Price
   ```

4. **Or create a custom button card:**
   ```yaml
   type: button
   name: Strategy Status
   entity: sensor.sessy_strategy_status
   icon: mdi:battery-heart-variant
   tap_action:
     action: more-info
   hold_action:
     action: none
   ```

### Expected Result

- Current strategy status is visible on your dashboard
- You can see all key entities at a glance
- Clicking on entities shows their detailed information

---

## Step 3: Price Chart

### What This Step Does

Create an interactive chart showing energy prices over time, with threshold lines to visualize when the strategy triggers.

### How to Do It

1. **Add ApexCharts card:**
   - Click **Add Card** → Search for "ApexCharts" or "Custom: ApexCharts Card"

2. **Configure the price chart:**
   ```yaml
   type: custom:apexcharts-card
   title: Energy Prices
   chart_type: line
   span:
     start: hour
   series:
     - entity: sensor.sessy_dnhh_energy_price
       name: Raw Price
       type: line
       stroke_width: 3
       color: var(--primary-color)
       group_by:
         func: avg
         duration: 1h
     - entity: sensor.sessy_dnhh_energy_price
       name: Import Price
       type: line
       stroke_width: 2
       color: var(--warning-color)
       group_by:
         func: avg
         duration: 1h
       transform: return x + 0.11;  # Add surcharge for import price
   ```

3. **Add threshold lines:**
   ```yaml
   apex_config:
     annotations:
       yaxis:
         - y: 0.39
           borderColor: '#ff0000'
           strokeDashArray: 4
           label:
             borderColor: '#ff0000'
             style:
               color: '#fff'
               background: '#ff0000'
             text: "Discharge Threshold"
           
         - y: -0.10
           borderColor: '#00ff00'
           strokeDashArray: 4
           label:
             borderColor: '#00ff00'
             style:
               color: '#fff'
               background: '#00ff00'
             text: "Charge Threshold"
   ```

### Complete Price Chart Example

```yaml
   type: custom:apexcharts-card
   title: Energy Prices with Thresholds
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: sensor.sessy_dnhh_energy_price
       name: Raw Price
       type: line
       stroke_width: 3
       color: '#009E73'  # Green for raw price
       group_by:
         func: avg
         duration: 1h
   
   apex_config:
     yaxis:
       - min: -0.2
         max: 0.7
         title:
           text: "Price (€/kWh)"
     annotations:
       yaxis:
         - y: 0.39
           borderColor: '#E63946'
           strokeDashArray: 4
           label:
             borderColor: '#E63946'
             style:
               color: '#fff'
               background: '#E63946'
             text: "Discharge > €0.39"
             
         - y: -0.10
           borderColor: '#009E73'
           strokeDashArray: 4
           label:
             borderColor: '#009E73'
             style:
               color: '#fff'
               background: '#009E73'
             text: "Charge < -€0.10"
   
   card_mod:
     style: |
       ha-card {
         border-left: 4px solid var(--primary-color);
       }
   ```

### Expected Result

- Interactive price chart showing raw prices
- Horizontal lines marking charge and discharge thresholds
- Visual indication of when strategy triggers occur
- Ability to hover for exact values

---

## Step 4: SOC Chart

### What This Step Does

Create a chart showing battery SOC over time, with target and floor indicators.

### How to Do It

```yaml
   type: custom:apexcharts-card
   title: Battery State of Charge
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: sensor.sessy_battery_alt9_state_of_charge
       name: SOC
       type: line
       stroke_width: 4
       color: '#0072B2'  # Blue for SOC
       group_by:
         func: avg
         duration: 1h
   
   apex_config:
     yaxis:
       - min: 0
         max: 100
         title:
           text: "SOC (%)"
     annotations:
       yaxis:
         - y: 70
           borderColor: '#0072B2'
           strokeDashArray: 4
           label:
             borderColor: '#0072B2'
             style:
               color: '#fff'
               background: '#0072B2'
             text: "Target: 70%"
             
         - y: 20
           borderColor: '#D55E00'
           strokeDashArray: 4
           label:
             borderColor: '#D55E00'
             style:
               color: '#fff'
               background: '#D55E00'
             text: "Floor: 20%"
             
         - y: 100
           borderColor: '#7BCAB4'
           strokeDashArray: 4
           label:
             borderColor: '#7BCAB4'
             style:
               color: '#fff'
               background: '#7BCAB4'
             text: "Ceiling: 100%"
   ```

### Expected Result

- SOC chart showing battery level over time
- Target, floor, and ceiling lines for reference
- Visual indication of battery charge/discharge patterns

---

## Step 5: Setpoint Chart

### What This Step Does

Create a chart showing strategy setpoints over time, with color coding by strategy branch.

### How to Do It

```yaml
   type: custom:apexcharts-card
   title: Strategy Setpoints
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: number.sessy_battery_alt9_power_setpoint
       name: Battery Setpoint
       type: line
       stroke_width: 2
       color: '#CC79A7'  # Purple for battery
       group_by:
         func: avg
         duration: 5min
     
     - entity: number.sessy_pwkn_grid_target
       name: Grid Target
       type: line
       stroke_width: 2
       color: '#D55E00'  # Orange for grid
       group_by:
         func: avg
         duration: 5min
   
   apex_config:
     yaxis:
       - title:
           text: "Power (W)"
     xaxis:
       type: datetime
   ```

### Advanced: Color by Strategy Branch

For more advanced visualization, you can use templates to color the setpoint based on the current strategy branch:

```yaml
   type: custom:apexcharts-card
   title: Battery Setpoint by Strategy
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: number.sessy_battery_alt9_power_setpoint
       name: Battery Setpoint
       type: line
       stroke_width: 3
       color: "var(--primary-color)"
       group_by:
         func: avg
         duration: 5min
       transform: |
         const status = entity('sensor.sessy_strategy_status');
         if (status === 'discharge') return {color: '#E63946'};
         if (status === 'cheap_charge') return {color: '#009E73'};
         if (status.includes('prepeak')) return {color: '#0072B2'};
         return {color: '#7BCAB4'};
   ```

### Expected Result

- Setpoint values over time
- Visual correlation with price and SOC patterns
- Understanding of when and how much the strategy charges/discharges

---

## Step 6: Combined Dashboard

### What This Step Does

Combine all the elements into a comprehensive dashboard layout.

### How to Do It

Here's a complete dashboard YAML configuration:

```yaml
# SessyStrategy HA Dashboard
views:
  - title: Battery Strategy
    path: battery-strategy
    badges: []
    cards:
      # Header
      - type: markdown
        content: "# 🔋 SessyStrategy HA Dashboard"
        style: |
          ha-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 20px;
          }

      # Status Overview Row
      - type: horizontal-stack
        cards:
          - type: custom:button-card
            name: Current Strategy
            entity: sensor.sessy_strategy_status
            icon: mdi:battery-heart-variant
            
          - type: custom:button-card
            name: Battery SOC
            entity: sensor.sessy_battery_alt9_state_of_charge
            icon: mdi:battery-90
            
          - type: custom:button-card
            name: Energy Price
            entity: sensor.sessy_dnhh_energy_price
            icon: mdi:currency-eur

      # Charts Row 1
      - type: horizontal-stack
        cards:
          - type: custom:apexcharts-card
            title: Energy Prices
            chart_type: line
            span:
              start: hour
              offset: -24h
            series:
              - entity: sensor.sessy_dnhh_energy_price
                name: Raw Price
                type: line
                stroke_width: 3
                color: '#009E73'
                group_by:
                  func: avg
                  duration: 1h
            apex_config:
              yaxis:
                - min: -0.2
                  max: 0.7
                  title:
                    text: "Price (€/kWh)"
              annotations:
                yaxis:
                  - y: 0.39
                    borderColor: '#E63946'
                    strokeDashArray: 4
                    label:
                      borderColor: '#E63946'
                      style:
                        color: '#fff'
                        background: '#E63946'
                      text: "Discharge"
                  - y: -0.10
                    borderColor: '#009E73'
                    strokeDashArray: 4
                    label:
                      borderColor: '#009E73'
                      style:
                        color: '#fff'
                        background: '#009E73'
                      text: "Charge"

          - type: custom:apexcharts-card
            title: Battery SOC
            chart_type: line
            span:
              start: hour
              offset: -24h
            series:
              - entity: sensor.sessy_battery_alt9_state_of_charge
                name: SOC
                type: line
                stroke_width: 4
                color: '#0072B2'
                group_by:
                  func: avg
                  duration: 1h
            apex_config:
              yaxis:
                - min: 0
                  max: 100
                  title:
                    text: "SOC (%)"
              annotations:
                yaxis:
                  - y: 70
                    borderColor: '#0072B2'
                    strokeDashArray: 4
                    label:
                      text: "Target"
                  - y: 20
                    borderColor: '#D55E00'
                    strokeDashArray: 4
                    label:
                      text: "Floor"

      # Charts Row 2
      - type: horizontal-stack
        cards:
          - type: custom:apexcharts-card
            title: Battery Setpoint
            chart_type: line
            span:
              start: hour
              offset: -24h
            series:
              - entity: number.sessy_battery_alt9_power_setpoint
                name: Battery Setpoint
                type: line
                stroke_width: 2
                color: '#CC79A7'
                group_by:
                  func: avg
                  duration: 5min
            apex_config:
              yaxis:
                - title:
                    text: "Power (W)"

          - type: custom:apexcharts-card
            title: Grid Target
            chart_type: line
            span:
              start: hour
              offset: -24h
            series:
              - entity: number.sessy_pwkn_grid_target
                name: Grid Target
                type: line
                stroke_width: 2
                color: '#D55E00'
                group_by:
                  func: avg
                  duration: 5min
            apex_config:
              yaxis:
                - title:
                    text: "Power (W)"

      # Strategy Details
      - type: entities
        title: Strategy Details
        entities:
          - sensor.sessy_strategy_status
          - entity: select.sessy_battery_alt9_power_strategy
            name: Strategy Mode
          - entity: number.sessy_battery_alt9_power_setpoint
            name: Battery Setpoint
          - entity: number.sessy_pwkn_grid_target
            name: Grid Target

      # Configuration Summary
      - type: markdown
        title: Configuration Summary
        content: |
          **Battery:** {{ states('sensor.sessy_battery_alt9_state_of_charge') }}% SOC  
          **Price:** €{{ states('sensor.sessy_dnhh_energy_price') }} /kWh  
          **Strategy:** {{ state_attr('sensor.sessy_strategy_status', 'active_branch') }}  
          **Season:** {{ state_attr('sensor.sessy_strategy_status', 'active_season') }}

      # Quick Actions
      - type: entities
        title: Quick Actions
        entities:
          - select.home_battery_mode
          - number.home_battery_setpoint
          - input_select.sessy_season_mode
```

### Dashboard Layout Tips

1. **Use horizontal stacks** for side-by-side charts
2. **Group related information** together
3. **Use consistent colors** across charts for the same data types
4. **Add spacing** between sections for better readability
5. **Consider mobile layout** — use vertical stacks for narrow screens

---

## Step 7: Advanced Dashboard Features

### Color-Coded by Strategy Branch

Create a chart that changes color based on the active strategy branch:

```yaml
   type: custom:apexcharts-card
   title: Strategy Timeline
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: sensor.sessy_strategy_status
       name: Strategy Branch
       type: line
       stroke_width: 0
       color: transparent
       group_by:
         func: last
         duration: 5min
       transform: |
         const status = entity('sensor.sessy_strategy_status');
         const branch = state_attr('sensor.sessy_strategy_status', 'active_branch');
         if (branch === 'discharge') return {y: 1, color: '#E63946'};
         if (branch === 'cheap_charge') return {y: 1, color: '#009E73'};
         if (branch.includes('prepeak')) return {y: 1, color: '#0072B2'};
         if (branch === 'evening_peak_excess') return {y: 1, color: '#D55E00'};
         return {y: 1, color: '#7BCAB4'};
   
   apex_config:
     yaxis:
       - show: false
     xaxis:
       type: datetime
     legend:
       show: true
       position: bottom
     annotations:
       yaxis:
         - y: 1
           borderColor: transparent
   ```

### Price and SOC Combined Chart

Show price and SOC on the same chart to see correlations:

```yaml
   type: custom:apexcharts-card
   title: Price vs SOC Correlation
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: sensor.sessy_dnhh_energy_price
       name: Price (€/kWh)
       type: line
       stroke_width: 2
       color: '#009E73'
       yaxis_index: 0
       group_by:
         func: avg
         duration: 1h
     
     - entity: sensor.sessy_battery_alt9_state_of_charge
       name: SOC (%)
       type: line
       stroke_width: 2
       color: '#0072B2'
       yaxis_index: 1
       group_by:
         func: avg
         duration: 1h
   
   apex_config:
     yaxis:
       - min: -0.2
         max: 0.7
         title:
           text: "Price (€/kWh)"
       - min: 0
         max: 100
         opposite: true
         title:
           text: "SOC (%)"
     annotations:
       yaxis:
         - y: 0.39
           borderColor: '#E63946'
           strokeDashArray: 4
           yaxis_index: 0
```

### Power Flow Chart

Create a stacked chart showing power flow:

```yaml
   type: custom:apexcharts-card
   title: Power Flow
   chart_type: line
   span:
     start: hour
     offset: -24h
   series:
     - entity: number.sessy_battery_alt9_power_setpoint
       name: Battery
       type: line
       stroke_width: 2
       color: '#CC79A7'
       group_by:
         func: avg
         duration: 5min
     
     - entity: number.sessy_pwkn_grid_target
       name: Grid
       type: line
       stroke_width: 2
       color: '#D55E00'
       group_by:
         func: avg
         duration: 5min
   
   apex_config:
     yaxis:
       - title:
           text: "Power (W)"
     legend:
       show: true
       position: bottom
```

---

## Step 8: Add Gauges and Meters

### What This Step Does

Add visual gauges and meters for quick at-a-glance information.

### How to Do It

**SOC Gauge:**
```yaml
   type: gauge
   entity: sensor.sessy_battery_alt9_state_of_charge
   name: Battery SOC
   min: 0
   max: 100
   unit: "%"
   segments:
     - from: 0
       to: 20
       color: red
     - from: 20
       to: 70
       color: yellow
     - from: 70
       to: 100
       color: green
```

**Price Meter:**
```yaml
   type: gauge
   entity: sensor.sessy_dnhh_energy_price
   name: Energy Price
   min: -0.2
   max: 0.7
   unit: "€/kWh"
   segments:
     - from: -0.2
       to: -0.10
       color: green
     - from: -0.10
       to: 0.39
       color: yellow
     - from: 0.39
       to: 0.7
       color: red
```

---

## Verification

To confirm your dashboard is working correctly:

1. [x] ApexCharts card is installed and available
2. [x] All charts display data without errors
3. [x] Status card shows current strategy information
4. [x] Price chart shows thresholds correctly
5. [x] SOC chart shows battery level with targets
6. [x] Setpoint charts show strategy decisions
7. [x] Dashboard loads quickly and is responsive
8. [x] All data updates in real-time (within 5 minutes)

---

## Success

[!note]
You've successfully created a comprehensive dashboard for monitoring SessyStrategy HA! Your dashboard now provides:

- **Real-time monitoring** of strategy state and key metrics
- **Historical visualization** of prices, SOC, and setpoints
- **Threshold indicators** showing when strategy triggers occur
- **Correlation views** to understand strategy behavior
- **Quick access** to configuration and control

### What You've Created

| Component | Purpose | Location |
|-----------|---------|----------|
| Status Overview | Quick glance at current state | Top of dashboard |
| Price Chart | Visualize energy prices with thresholds | Charts section |
| SOC Chart | Track battery level over time | Charts section |
| Setpoint Charts | Monitor strategy decisions | Charts section |
| Strategy Timeline | See when different strategies activate | Advanced section |
| Combined Views | Correlate price, SOC, and decisions | Advanced section |

### Next Steps

- **[Tune Price Thresholds](../how-to/tune-price-thresholds.md)** — Adjust thresholds based on your dashboard observations
- **[Configure Seasonal Mode](../how-to/configure-seasonal-mode.md)** — Set up seasonal adjustments
- **[Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)** — Add dashboard controls for real-time tuning
- **[Share Your Dashboard](https://github.com/your-repo/discussions)** — Share your creation with the community

### Pro Tips

1. **Save your dashboard YAML** — Export your dashboard configuration for backup
2. **Create multiple dashboards** — One for overview, one for detailed analysis
3. **Use themes** — Match your dashboard colors to your Home Assistant theme
4. **Add conditional cards** — Show/hide cards based on strategy state
5. **Share with the community** — Others can learn from your setup

### Example: Conditional Card

Show a warning when battery is low:
```yaml
   type: conditional
   conditions:
     - entity: sensor.sessy_battery_alt9_state_of_charge
       state_not: unavailable
       below: 25
   card:
     type: markdown
     content: "Battery SOC is low! Consider adjusting charge settings."
     style: |
       ha-card {
         background: #ffcc00;
         color: #333;
         text-align: center;
         padding: 15px;
       }
```

---

## Feedback

Found an issue or have suggestions for this tutorial? [Open an issue](https://github.com/your-repo/issues) or contribute improvements via pull request.

---

*Last updated: 2026-08-01*
*Tutorial created: 2026-08-01*