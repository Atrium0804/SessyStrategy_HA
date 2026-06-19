# Sessy Battery Strategy — Home Assistant Integration

An AppDaemon-based charging strategy for the Sessy home battery that minimises solar export, avoids expensive grid imports, and captures value during extreme price events — all automatically, based on real-time dynamic energy prices.

---

## Table of contents

1. [How the strategy works](#1-how-the-strategy-works)
2. [Setpoint types explained](#2-setpoint-types-explained)
3. [Summer operation example](#3-summer-operation-example)
4. [Winter operation example](#4-winter-operation-example)
5. [Installation](#5-installation)
6. [Configuration reference](#6-configuration-reference)
7. [Entity reference](#7-entity-reference)
8. [ApexCharts dashboard](#8-apexcharts-dashboard)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. How the strategy works

The strategy runs every 5 minutes and decides what the Sessy should do right now, based on current state of charge and the live energy price. It follows a strict priority order:

```
Priority 1 — Price spike (import price > €0.50)
    → Battery setpoint: discharge toward SOC floor, spread over 2 hours

Priority 2 — Negative / very cheap price (raw price < −€0.10)
    → Battery setpoint: charge toward 100% SOC, rate spread over the
      remaining run of cheap hours

Priority 3 — Pre-peak window (season-aware), SOC below target, and a
             worthwhile evening peak ahead
    → Battery setpoint: charge toward 90% SOC, spread over a
      season-specific window
      (skipped if the expected peak does not beat the current import
       price by at least the arbitrage margin)

Priority 4 — Default (all other times)
    → Grid setpoint 0W: absorb all PV into battery, block export
```

### Why grid setpoint 0W as the default?

Exporting solar power and then reimporting it later costs an extra **€0.11/kWh** in energy tax surcharge. A grid setpoint of 0W tells the Sessy to keep the meter at zero — all available PV generation is stored in the battery first. Only when the battery is full does surplus PV flow to the grid. This eliminates the expensive export/reimport round trip during sunny hours.

### Why spread setpoints over 2 hours?

Running the battery and inverter at partial power has two important advantages:

- **Efficiency:** inverter copper losses scale with the square of current. Half power is roughly four times more efficient per watt than full power. Battery internal resistance losses also decrease at lower C-rates.
- **PV self-consumption during the pre-peak window:** a gentle charge rate during 16:00–18:00 leaves headroom for residual solar to contribute, so the grid only fills the actual gap.

### Setpoint formula

Both the pre-peak charge and the price-spike discharge use the same proportional approach, recalculated every 5 minutes:

```
charge setpoint (W)    = (SOC_target − SOC_current) / 100 × capacity_Wh / window_hours
discharge setpoint (W) = (SOC_current − SOC_floor)  / 100 × capacity_Wh / window_hours
```

Both are capped at 40% C-rate (2,000 W for a 5 kWh battery) and the hardware maximum of 2,200 W. The rate tapers naturally as SOC approaches its target, acting as a simple proportional controller.

### Cheap-window charging

When the raw price drops below `PRICE_CHARGE` (−€0.10), the strategy charges from the grid toward a ceiling of `CHEAP_SOC_TARGET` (100%). Rather than always pulling maximum power, it counts how many consecutive upcoming hours stay below the threshold and spreads the remaining gap across them:

```
cheap charge (W) = (CHEAP_SOC_TARGET − SOC_current) / 100 × capacity_Wh / cheap_hours_remaining
```

A short single-hour dip therefore charges hard to capture it, while a long cheap block charges gently and efficiently. The same 40% C-rate and hardware caps apply, and charging stops once the ceiling is reached. Because the rate is recalculated every 5 minutes, it self-corrects as SOC rises and the remaining cheap hours count down.

### Pre-peak break-even guard

Pre-peak charging (Priority 3) buys energy now to discharge it during the evening. To avoid the marginal-gain trap — buying at, say, €0.46 import only to discharge at €0.47 — the strategy first checks the expected evening peak. It scans the price schedule for the highest raw price in the evening window (`EVENING_PEAK_START`–`EVENING_PEAK_END`) and only charges if:

```
expected_peak_raw − import_price_now ≥ MIN_ARBITRAGE_MARGIN
```

If the spread is too small, it skips the charge and falls through to the 0W default, still absorbing any residual PV. This needs only a single lookup against price data the integration already provides — no forward optimisation, no extra dependencies.

### Price note

The Sessy integration exposes **raw export prices** (what the grid pays you). The consumer import price is raw + €0.11 surcharge. The strategy uses raw prices throughout:

| Condition | Raw price threshold | Import price equivalent |
|---|---|---|
| Discharge override | > €0.39/kWh | > €0.50/kWh |
| Cheap charge | < −€0.10/kWh | < €0.01/kWh |

---

## 2. Setpoint types explained

The Sessy supports two control modes, switched via `select.sessy_battery_alt9_power_strategy`:

### `nom` — Grid setpoint (strategy = nom)

Controls the power at the **grid connection**. The battery responds to keep the meter at the target value. PV generation is consumed by the house first; the battery covers any remaining gap or absorbs surplus.

- Set via: `number.sessy_pwkn_grid_target` (W, negative = import, positive = export)
- Used for: default 0W operation
- Effect of 0W: all PV is forced into the battery; export is blocked until battery is full

### `api` — Battery setpoint (strategy = api)

Controls the **battery charge/discharge power** directly. The grid covers any mismatch between battery power and household load. PV generation still flows to the house and battery; grid covers the rest.

- Set via: `number.sessy_battery_alt9_power_setpoint` (W, negative = charge, positive = discharge)
- Used for: pre-peak SOC targeting, price-spike discharge, cheap-window charging
- Effect: battery runs at the exact specified power; grid acts as balancer

---

## 3. Summer operation example

**Conditions:** sunny day, PV production 1,500–2,000 W peak, 5 kWh battery

| Time | Price (raw) | Strategy | Setpoint | SOC | What happens |
|---|---|---|---|---|---|
| 00:00–06:00 | €0.05–0.08 | Grid | 0 W | ~20% | Battery rests. Grid covers night load. |
| 06:00–09:00 | €0.13–0.22 | Grid | 0 W | ~20% | No solar yet. Battery conserved. |
| 09:00–16:00 | €0.08–0.11 | Grid | 0 W | 20%→90% | PV rises. Grid setpoint 0W forces all PV into battery. No export. Battery fills by early afternoon on a good day. |
| 16:00–18:00 | €0.08–0.11 | Battery | −300–800 W | 85%→90% | If battery not yet full, spread charge from grid. Rate = (90−SOC)/100 × 5000 / 2. Residual PV still contributes. |
| 18:00–22:00 | €0.13–0.47 | Battery* | +1500 W | 90%→20% | Battery discharges to cover evening load. *If price > €0.39: discharge setpoint active. |
| 22:00–24:00 | €0.15–0.16 | Grid | 0 W | ~20% | Battery rests. Prices moderate, no action. |

**Example price-spike event (today's data, 20:00–21:00, raw €0.46):**

At 20:00 the raw price hits €0.46 (import €0.57), triggering the discharge override. With SOC at 80%:

```
available_Wh = (80 − 20) / 100 × 5000 = 3000 Wh
setpoint     = min(3000 / 2, 2000, 2200) = 1500 W discharge
```

The battery feeds 1,500 W back through the inverter, reducing grid import to near zero during the most expensive hour of the day.

---

## 4. Winter operation example

**Conditions:** low PV (200–600 W on good days), higher household load due to heating, no significant midday solar peak

In winter the strategy shifts significantly: solar cannot reliably fill the battery during the day, so the overnight cheap-price window becomes the primary charge opportunity.

| Time | Price (raw) | Strategy | Setpoint | SOC | What happens |
|---|---|---|---|---|---|
| 00:00–06:00 | €0.07–0.10 | Battery | 0 to −2200 W | 40%→100% | If price dips below −€0.10 (occasional in winter), charge toward 100% spread over the run of cheap hours. Otherwise rest. |
| 06:00–09:00 | €0.30–0.55 | Battery* | +1000–1500 W | 80%→45% | Morning heating load. *If price > €0.39: discharge override active, covers heating demand from battery. |
| 09:00–14:00 | €0.14–0.25 | Grid | 0 W | 45%→55% | Limited PV absorbed. Grid setpoint 0W prevents export of scarce winter solar. Grid covers remainder of load. |
| 14:00–16:00 | €0.16–0.22 | Grid | 0 W | 55%→60% | Prices rising. Continue absorbing any PV. |
| 16:00–18:00 | €0.35–0.52 | Battery | −750–1250 W | 60%→90% | Pre-peak charge. With lower starting SOC than summer, rate is higher. Watch total grid cost: buying at €0.46 import to discharge at €0.57 later only breaks even if the spike is sufficiently above the pre-peak price. |
| 18:00–23:00 | €0.48–0.68 | Battery* | +1250–1500 W | 90%→40% | Evening heating peak. Battery covers load. *Discharge override fires if price > €0.39. |
| 23:00–24:00 | €0.10–0.14 | Grid | 0 W | ~40% | Rest. Assess whether overnight cheap window will occur. |

**Winter-specific considerations:**

- The pre-peak window sometimes buys grid energy at €0.46+ import, only to discharge it at €0.57+ — a margin of €0.11, which is exactly the surcharge. In marginal cases this barely breaks even. Consider raising `PRICE_DISCHARGE` or narrowing `PREPEAK_START`/`PREPEAK_END` in winter months if prices are consistently high from 16:00 onward.
- The discharge floor `SOC_FLOOR = 20%` leaves 1 kWh in reserve. In cold weather with higher overnight heating loads, consider raising this to 30% so there is always a morning reserve.
- Sessy's own dynamic schedule (`sensor.sessy_dnhh_power_schedule`) is worth monitoring in winter — it can spot overnight cheap windows that the fixed threshold misses.

---

## 5. Installation

### Prerequisites

- Home Assistant with the [Sessy integration](https://github.com/PimDoos/ha-sessy) installed and configured
- [AppDaemon 4](https://appdaemon.readthedocs.io/) installed as a Home Assistant add-on (HAOS) or in a separate container (docker compose)

### Step 1 — Install AppDaemon

In Home Assistant, go to **Settings → Add-ons → Add-on store** and search for **AppDaemon 4**. Install and start it. Enable **Start on boot** and **Watchdog**.

### Step 2 — Copy the strategy file

Copy `sessy_strategy.py` to your AppDaemon apps directory. If you use the AppDaemon add-on, this is typically:

```
/config/appdaemon/apps/sessy_strategy.py
```

Via SSH or the Samba share, or using the File Editor add-on.

### Step 3 — Register and configure the app

Copy `apps.yaml` to `/config/appdaemon/apps/apps.yaml` (or merge its contents). At minimum, map the entity IDs to your own Sessy entities — the defaults use this author's entity suffixes (`alt9`, `dnhh`, `pwkn`) and will **not** match your installation:

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  # Map these to your own Sessy entities:
  strategy_select: select.sessy_battery_<id>_power_strategy
  grid_target: number.sessy_<id>_grid_target
  battery_setpoint: number.sessy_battery_<id>_power_setpoint
  soc_sensor: sensor.sessy_battery_<id>_state_of_charge
  price_sensor: sensor.sessy_<id>_energy_price
```

All tunables (SOC targets, price thresholds, time windows) are optional and fall back to sensible defaults — see [Configuration reference](#6-configuration-reference) for the full list.

**Optional — HA helpers:** copy `sessy_helpers.yaml` into `/config/packages/` (enable `packages: !include_dir_named packages` in `configuration.yaml`) to get:

- `input_boolean.sessy_strategy_enabled` (master on/off)
- `input_select.sessy_season_mode` (auto/summer/winter)
- optional live `input_number` tuning sliders

Reference these in `apps.yaml` (`enable_switch:`, `season_mode_entity:`, and the `*_entity` keys) to control behavior from the HA UI without restarting AppDaemon.

### Step 4 — Verify AppDaemon configuration

Ensure `/config/appdaemon/appdaemon.yaml` contains your time zone and Home Assistant connection. A minimal example:

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

Generate a long-lived access token in Home Assistant under **Profile → Long-lived access tokens**.

### Step 5 — Restart AppDaemon

Restart the AppDaemon add-on. Within a few seconds you should see log output in the AppDaemon log:

```
INFO sessy_strategy: Sessy strategy starting up
INFO sessy_strategy: Hour=14  SOC=72%  Raw price=0.02590  Import price=0.13590
INFO sessy_strategy: DEFAULT: grid setpoint 0W — absorb solar, block export
```

AppDaemon logs are accessible via **Settings → Add-ons → AppDaemon → Log**.

### Step 6 — Verify entity control

Check that the strategy is writing to the correct entities by watching the state of:

- `select.sessy_battery_alt9_power_strategy` — should switch between `nom` and `api`
- `number.sessy_pwkn_grid_target` — should show 0 during normal daytime operation
- `number.sessy_battery_alt9_power_setpoint` — should show a negative value during pre-peak charging

---

## 6. Configuration reference

All tunables and entity IDs are set as app arguments in `apps.yaml` — no need to edit the Python. Every value is optional except the entity IDs, which must match your installation. Defaults are shown below:

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy

  capacity_wh: 5000          # Battery capacity in Wh
  max_power_w: 2200          # Inverter/battery max power in W
  c_rate_cap: 0.40           # Max C-rate for spread setpoints (0.40 = 40%)
  soc_target: 90             # % SOC to reach before the evening peak
  soc_floor: 20              # % SOC floor — never discharge below this
  cheap_soc_target: 100      # % SOC ceiling for cheap-price charging
  surcharge: 0.11            # Import surcharge €/kWh (raw export → import)
  price_discharge: 0.39      # Raw price above which to force discharge
  price_charge: -0.10        # Raw price below which to charge from grid
  min_arbitrage_margin: 0.05 # Min €/kWh spread to justify pre-peak charge
  prepeak_start: 16          # Start hour of pre-peak charge window (local)
  prepeak_end: 18            # End hour of pre-peak charge window (local)
  prepeak_window_h: 2.0      # Spread window for pre-peak charge (hours)
  discharge_window_h: 2.0    # Spread window for price-spike discharge (hours)
  evening_peak_start: 18     # Start hour of evening peak (break-even check)
  evening_peak_end: 23       # End hour of evening peak (break-even check)

  # Season mode: auto | summer | winter
  season_mode: auto
  season_day_start: 8
  season_day_end: 18
  season_auto_fallback: winter

  # Optional winter-specific overrides (used in winter mode)
  soc_floor_winter: 30
  prepeak_start_winter: 14
  prepeak_end_winter: 18
  prepeak_window_h_winter: 4.0

  # Entity IDs — map to your own Sessy entities:
  strategy_select: select.sessy_battery_alt9_power_strategy
  grid_target: number.sessy_pwkn_grid_target
  battery_setpoint: number.sessy_battery_alt9_power_setpoint
  soc_sensor: sensor.sessy_battery_alt9_state_of_charge
  price_sensor: sensor.sessy_dnhh_energy_price
  status_sensor: sensor.sessy_strategy_status

  # Optional master enable switch (see sessy_helpers.yaml):
  enable_switch: input_boolean.sessy_strategy_enabled

  # Optional live season mode selector (input_select auto/summer/winter):
  season_mode_entity: input_select.sessy_season_mode
```

Changes to `apps.yaml` are picked up automatically by AppDaemon (it reloads the app); no restart required.

### Live tuning from the HA UI

Five of the most frequently adjusted values can optionally be driven by `input_number` helpers instead of static `apps.yaml` values, so you can change them from a dashboard (or your phone) with no file editing and no restart:

| `apps.yaml` key | Helper (from `sessy_helpers.yaml`) |
|---|---|
| `soc_target_entity` | `input_number.sessy_soc_target` |
| `soc_floor_entity` | `input_number.sessy_soc_floor` |
| `price_discharge_entity` | `input_number.sessy_price_discharge` |
| `price_charge_entity` | `input_number.sessy_price_charge` |
| `min_arbitrage_margin_entity` | `input_number.sessy_min_arbitrage_margin` |
| `season_mode_entity` | `input_select.sessy_season_mode` |

The app reads each helper every cycle and **falls back to the static value** above if the helper is missing or unreadable. Omit any `*_entity` line to keep that value `apps.yaml`-only. Because the helpers are real HA entities, they can also be driven by automations (e.g. raise `soc_floor` on cold days) and graphed in history. The structural settings (`capacity_wh`, entity IDs, time windows) remain `apps.yaml`-only by design.

### Season mode toggle (summer/winter/auto)

The strategy supports a season toggle:

- `season_mode: summer` uses the base values (`soc_floor`, `prepeak_start`, `prepeak_end`, `prepeak_window_h`)
- `season_mode: winter` applies winter overrides if configured (`soc_floor_winter`, `prepeak_start_winter`, `prepeak_end_winter`, `prepeak_window_h_winter`)
- `season_mode: auto` infers season from **today's minimum raw price hour**:
  - minimum during daytime `[season_day_start, season_day_end)` => summer
  - minimum outside that window => winter

If `auto` cannot infer (missing price data), `season_auto_fallback` is used (`winter` by default).

You can also control this live from HA UI by setting:

- `season_mode_entity: input_select.sessy_season_mode`

where the `input_select` options are `auto`, `summer`, and `winter`.

**Seasonal tuning suggestions:**

| Parameter | Summer | Winter |
|---|---|---|
| `soc_target` | 90% | 90% |
| `soc_floor` | 20% | 30% |
| `prepeak_start` | 16 | 14 |
| `prepeak_end` | 18 | 18 |
| `prepeak_window_h` | 2.0 | 4.0 |
| `price_discharge` | 0.39 | 0.39 |

---

## 7. Entity reference

The entity IDs below are the **defaults** (this author's installation). Override any of them in `apps.yaml` to match your own — see [Configuration reference](#6-configuration-reference).

### Sensors (read)

| Entity | Description | Used for |
|---|---|---|
| `sensor.sessy_battery_alt9_state_of_charge` | Current SOC in % | Setpoint calculation |
| `sensor.sessy_dnhh_energy_price` | Current raw export price €/kWh; full schedule in `energy_prices` attribute | Price decisions |
| `sensor.sessy_dnhh_power_schedule` | Sessy's own dynamic schedule in `dynamic_schedule` attribute | Reference / monitoring |
| `sensor.sessy_pwkn_p1_power` | Actual grid power W (negative = export) | Dashboard monitoring |
| `sensor.sessy_battery_alt9_pv_power` | Current PV production W | Dashboard monitoring |
| `sensor.sessy_battery_alt9_power` | Current battery power W | Dashboard monitoring |
| `sensor.sessy_battery_alt9_load_power` | Household load W | Dashboard monitoring |
| `sensor.sessy_battery_alt9_system_state` | System state (running, full, empty…) | Health monitoring |
| `sensor.sessy_strategy_status` | App status sensor published by AppDaemon (`state` = active season) | Season/inference/debug visibility |

### Controls (write)

| Entity | Description | Values |
|---|---|---|
| `select.sessy_battery_alt9_power_strategy` | Active control strategy | `nom` (grid setpoint), `api` (battery setpoint) |
| `number.sessy_pwkn_grid_target` | Grid power target W | −20000 to +20000 (negative = import) |
| `number.sessy_battery_alt9_power_setpoint` | Battery power setpoint W | −2200 to +2200 (negative = charge, positive = discharge) |
| `input_boolean.sessy_strategy_enabled` | Optional master switch (`enable_switch`) | `on` = run, `off` = pause the strategy |
| `input_number.sessy_soc_target` | Optional live SOC target (`soc_target_entity`) | 0–100 % |
| `input_number.sessy_soc_floor` | Optional live SOC floor (`soc_floor_entity`) | 0–100 % |
| `input_number.sessy_price_discharge` | Optional live discharge threshold (`price_discharge_entity`) | €/kWh |
| `input_number.sessy_price_charge` | Optional live cheap-charge threshold (`price_charge_entity`) | €/kWh |
| `input_number.sessy_min_arbitrage_margin` | Optional live arbitrage margin (`min_arbitrage_margin_entity`) | €/kWh |
| `input_select.sessy_season_mode` | Optional live season mode (`season_mode_entity`) | `auto`, `summer`, `winter` |

---

## 8. ApexCharts dashboard

Install the [ApexCharts Card](https://github.com/RomRider/apexcharts-card) via HACS before using these examples.

### 8.1 — Energy price with strategy triggers

Shows the full day's price curve with dynamic threshold lines driven by HA helpers (`input_number.sessy_price_discharge` and `input_number.sessy_price_charge`). The price y-axis uses soft bounds around the common raw-price band.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Energy price & strategy triggers
  show_states: true
  colorize_states: true
graph_span: 24h
span:
  start: day
now:
  show: true
  label: now
apex_config:
  yaxis:
    - min: ~-0.05
      max: ~0.25
series:
  - entity: sensor.sessy_dnhh_energy_price
    name: Raw export price
    color: "#EF9F27"
    type: line
    stroke_width: 2
    float_precision: 4
    data_generator: |
      const prices = entity.attributes.energy_prices;
      if (!prices) return [];
      return Object.entries(prices).map(([ts, val]) => ({
        x: new Date(ts).getTime(),
        y: parseFloat(val)
      }));
  - entity: input_number.sessy_price_discharge
    name: Discharge trigger (dynamic)
    color: "#E24B4A"
    type: line
    stroke_width: 1.5
    stroke_dash: 5
  - entity: input_number.sessy_price_charge
    name: Cheap charge trigger (dynamic)
    color: "#1D9E75"
    type: line
    stroke_width: 1.5
    stroke_dash: 5
```

### 8.2 — Battery SOC and power flows

Shows SOC alongside PV production, battery power, and grid power on a shared timeline. Positive battery power = discharge, negative = charge.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Battery SOC & power flows
graph_span: 24h
span:
  start: day
now:
  show: true
  label: now
apex_config:
  yaxis:
    - id: soc
      min: 0
      max: 100
      title:
        text: SOC (%)
      opposite: true
    - id: power
      title:
        text: Power (W)
series:
  - entity: sensor.sessy_battery_alt9_state_of_charge
    name: State of charge
    color: "#1D9E75"
    type: area
    opacity: 0.15
    stroke_width: 2
    yaxis_id: soc
    unit: "%"
  - entity: sensor.sessy_battery_alt9_pv_power
    name: PV production
    color: "#EF9F27"
    type: line
    stroke_width: 1.5
    yaxis_id: power
  - entity: sensor.sessy_battery_alt9_power
    name: Battery power
    color: "#3B8BD4"
    type: line
    stroke_width: 1.5
    yaxis_id: power
    transform: "return x * -1;"
    # Inverted so negative = charge (consistent with convention)
  - entity: sensor.sessy_pwkn_p1_power
    name: Grid power
    color: "#9F77DD"
    type: line
    stroke_width: 1.5
    yaxis_id: power
```

### 8.3 — Sessy dynamic schedule vs actual battery power

Compares what Sessy's own dynamic strategy planned against what the battery actually did. Useful for validating that your override strategy is outperforming the default.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Dynamic schedule vs actual battery power
graph_span: 24h
span:
  start: day
now:
  show: true
  label: now
series:
  - entity: sensor.sessy_dnhh_power_schedule
    name: Sessy dynamic schedule
    color: "#888780"
    type: line
    stroke_width: 1.5
    stroke_dash: 4
    data_generator: |
      const schedule = entity.attributes.dynamic_schedule;
      if (!schedule) return [];
      const entries = Object.entries(schedule).map(([ts, val]) => ({
        x: new Date(ts).getTime(),
        y: parseFloat(val)
      }));
      // Extend each step value to the next step (step chart)
      const result = [];
      for (let i = 0; i < entries.length; i++) {
        result.push(entries[i]);
        if (i < entries.length - 1) {
          result.push({ x: entries[i + 1].x - 1, y: entries[i].y });
        }
      }
      return result;
  - entity: sensor.sessy_battery_alt9_power
    name: Actual battery power
    color: "#3B8BD4"
    type: line
    stroke_width: 2
```

### 8.4 — Combined strategy overview dashboard

A full-width card combining price, SOC, and all power flows in a single view. Suitable as a main energy dashboard panel.

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Sessy strategy overview
graph_span: 24h
span:
  start: day
now:
  show: true
  label: now
apex_config:
  chart:
    height: 400
  yaxis:
    - id: power
      min: -2500
      max: 2500
      title:
        text: Power (W)
    - id: price
      opposite: true
      min: ~-0.05
      max: ~0.25
      title:
        text: Price (€/kWh)
    - id: soc
      opposite: true
      min: 0
      max: 100
      show: false
series:
  - entity: sensor.sessy_dnhh_energy_price
    name: Energy price
    color: "#EF9F2780"
    type: area
    opacity: 0.3
    stroke_width: 1.5
    yaxis_id: price
    float_precision: 4
    data_generator: |
      const prices = entity.attributes.energy_prices;
      if (!prices) return [];
      return Object.entries(prices).map(([ts, val]) => ({
        x: new Date(ts).getTime(),
        y: parseFloat(val)
      }));
  - entity: input_number.sessy_price_discharge
    name: Discharge trigger
    color: "#E24B4A"
    type: line
    stroke_width: 1.2
    stroke_dash: 5
    yaxis_id: price
  - entity: input_number.sessy_price_charge
    name: Cheap charge trigger
    color: "#1D9E75"
    type: line
    stroke_width: 1.2
    stroke_dash: 5
    yaxis_id: price
  - entity: sensor.sessy_battery_alt9_state_of_charge
    name: SOC
    color: "#1D9E75"
    type: line
    stroke_width: 2
    yaxis_id: soc
    unit: "%"
  - entity: sensor.sessy_battery_alt9_pv_power
    name: PV
    color: "#EF9F27"
    type: area
    opacity: 0.2
    stroke_width: 1.5
    yaxis_id: power
  - entity: sensor.sessy_battery_alt9_power
    name: Battery
    color: "#3B8BD4"
    type: line
    stroke_width: 1.5
    yaxis_id: power
  - entity: sensor.sessy_pwkn_p1_power
    name: Grid
    color: "#9F77DD"
    type: line
    stroke_width: 1.5
    yaxis_id: power
  - entity: sensor.sessy_battery_alt9_load_power
    name: Load
    color: "#D85A30"
    type: line
    stroke_width: 1
    stroke_dash: 3
    yaxis_id: power
```

---

## 9. Troubleshooting

**Strategy is not switching modes**

Check that the `select.sessy_battery_alt9_power_strategy` entity is writable from HA developer tools. Try setting it manually to `api` via **Developer Tools → Services → select.select_option**. If it reverts immediately, the Sessy firmware may be overriding API control — check `binary_sensor.sessy_battery_alt9_strategy_override`.

**Prices are not updating**

The `energy_prices` attribute on `sensor.sessy_dnhh_energy_price` is populated by the Sessy integration when the dongle has internet access. Check `sensor.sessy_dnhh_wifi_rssi` and confirm the dongle is online. Prices for the next day typically arrive after 14:00 CET.

**AppDaemon app not loading**

Check the AppDaemon log for import errors. Ensure the file is named exactly `sessy_strategy.py` and the `apps.yaml` entry matches the filename (`module: sessy_strategy`). Python syntax errors appear in the log with a line number.

**Battery not charging during pre-peak window**

Check the AppDaemon log at 16:00 — it will show the SOC, target, and calculated setpoint. If the strategy is overriding with a price trigger, the price at that hour may be above `PRICE_DISCHARGE`. Check the raw price in the `energy_prices` attribute for the 16:00 slot.

**Pre-peak charge not reaching target by 18:00**

If SOC starts too low (below ~50%) the 2-hour spread may be insufficient. The setpoint is capped at 40% C-rate (2,000 W for 5 kWh), which delivers at most 4 kWh in 2 hours — meaning you can recover at most 80% SOC from empty. If you regularly start the window below 50%, consider extending `PREPEAK_WINDOW_H` to 3 or 4 and setting `PREPEAK_START` to 14 or 15.

**AppDaemon log says "Could not read SOC or price"**

The Sessy integration entity returned an unavailable or unknown state. This is usually transient — the app will retry in 5 minutes. If persistent, check the Sessy dongle connection and HA integration health.
