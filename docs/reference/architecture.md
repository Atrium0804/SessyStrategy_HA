# Architecture

*Last updated: 2026-08-01 | Part of [Reference Documentation](../)*

---

## Overview

SessyStrategy is an AppDaemon application that implements a price-optimized battery charging strategy for the Sessy home battery system. It follows a **top-down priority chain** architecture, where the first matching condition wins and sets the battery behavior for that cycle.

**Core philosophy:** Lean, deterministic, self-correcting. No forecasting, no complex optimization — just simple thresholds that capture most of the value.

---

## AppDaemon Application Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    AppDaemon Application                       │
├─────────────────────────────────────────────────────────────┤
│  1. initialize() — Configuration & Setup                       │
│     ├─ Load tunables from apps.yaml                            │
│     ├─ Load entity IDs                                         │
│     ├─ Set up live input listeners                              │
│     ├─ Schedule initial run (30s delay)                        │
│     └─ Schedule recurring run (every 5 minutes)                │
│                                                                 │
│  2. update_strategy() — Main Logic                              │
│     ├─ Check critical entities available                        │
│     ├─ Resolve active mode                                      │
│     ├─ Handle manual/standby modes (early return)              │
│     └─ Run priority chain for "optimized" mode                │
│                                                                 │
│  3. Helper Methods                                             │
│     ├─ Setpoint calculators (_charge, _discharge, etc.)         │
│     ├─ Sensor readers (_get_soc, _get_current_price)          │
│     ├─ Actuator helpers (_set_grid, _set_battery)              │
│     └─ Utility methods (_tunable, _seasonal_value, etc.)       │
│                                                                 │
│  4. Callback Methods                                           │
│     └─ _on_input_change() — Live input change handler           │
└─────────────────────────────────────────────────────────────┘
```

---

## Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         SessyStrategy                            │
│  (extends appdaemon.plugins.hass.hassapi.Hass)                 │
├─────────────────────────────────────────────────────────────┤
│  Tunables (from args)                                           │
│  ├── Battery/Hardware: capacity_wh, max_power_w               │
│  ├── SOC Targets: soc_target, soc_floor, cheap_soc_target        │
│  ├── Pricing: surcharge, price_discharge, price_charge          │
│  │       min_arbitrage_margin                                   │
│  ├── Windows: prepeak_start, prepeak_end, prepeak_window_h      │
│  │           evening_peak_start, evening_peak_end               │
│  ├── Season: season_mode, season_day_start, season_day_end     │
│  │          season_auto_fallback                                │
│  └── Winter overrides: soc_floor_winter, prepeak_start_winter  │
│                       prepeak_end_winter, prepeak_window_h_winter│
│                                                                 │
│  Entity IDs (from args)                                         │
│  ├── Controls: strategy_select, grid_target, battery_setpoint  │
│  ├── Sensors: soc_sensor, price_sensor, status_sensor          │
│  ├── Mode: mode_select, setpoint_entity                         │
│  └── Live: soc_target_entity, soc_floor_entity, ...            │
│                                                                 │
│  State                                                         │
│  ├── _last_active_season: str                                  │
│  └── _rerun_timer: timer object                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Callback Architecture

### Timer Management

The app uses AppDaemon's timer system for scheduling:

1. **Initial Run**: Delayed by 30 seconds to allow Home Assistant to fully initialize
   ```python
   self.run_in(self.update_strategy, 30)
   ```

2. **Recurring Run**: Every 5 minutes
   ```python
   self.run_every(self.update_strategy, self.datetime() + timedelta(seconds=30), 5 * 60)
   ```

3. **Debounced Re-run**: After live input changes
   ```python
   self._rerun_timer = self.run_in(self._rerun_now, self.rerun_debounce_s)
   ```

### Live Input Listeners

The app listens for state changes on all configured live input entities:

```python
live_inputs = [
    self.mode_select,
    self.setpoint_entity,
    self.soc_target_entity,
    self.soc_floor_entity,
    # ... all other *_entity configs
]
for entity in live_inputs:
    if entity:
        self.listen_state(self._on_input_change, entity)
```

**Listener behavior:**
- Triggered when any watched entity state changes
- Checks if old != new (ignores no-op changes)
- Cancels any pending re-run timer
- Schedules new re-run after debounce delay
- Only one re-run happens even if multiple inputs change rapidly

---

## Decision Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    update_strategy()                           │
├─────────────────────────────────────────────────────────────┤
│  1. Check critical entities (SOC, price)                       │
│     └─ If missing: log warning, return                          │
│                                                                 │
│  2. Resolve mode from mode_select                              │
│     └─ Normalizes to: optimized, grid_setpoint, battery_setpoint│
│         sessy_dynamic, eco, idle                                │
│                                                                 │
│  3. Mode Dispatch                                               │
│     ├── mode == "disabled" → return                            │
│     ├── mode == "idle" → _apply_standby(idle_option, "idle")    │
│     ├── mode == "sessy_dynamic" → _apply_standby(dynamic_opt, ..)│
│     ├── mode == "eco" → _apply_standby(eco_option, "eco")      │
│     ├── mode == "grid_setpoint" → set manual grid target        │
│     ├── mode == "battery_setpoint" → set manual battery target  │
│     └── mode == "optimized" → run priority chain                 │
│                                                                 │
│  4. Priority Chain (optimized mode only)                       │
│     ├── P1: price > price_discharge → discharge               │
│     ├── P2: price < price_charge → cheap charge                │
│     ├── P3: prepeak window, SOC < target, margin OK → charge    │
│     │       └─ P3a: SOC >= target → hold at 0W                │
│     │       └─ P3b: spread < margin → hold at 0W               │
│     ├── P4: evening peak, SOC > target, no spike left → export │
│     │       └─ P4a: remaining price < threshold → hold at 0W    │
│     └── P5: default → grid setpoint 0W                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Method Categories

### Initialization Methods

| Method | Purpose | Called |
|---|---|---|
| `initialize()` | Set up app, load config, schedule runs | On app start |
| `_optional_float_arg(key)` | Parse optional float from args | During init |
| `_optional_int_arg(key)` | Parse optional int from args | During init |

### Main Logic Methods

| Method | Purpose | Called |
|---|---|---|
| `update_strategy(kwargs)` | Main decision engine | Every 5 min + on input change |
| `_active_mode()` | Resolve current mode from entity | Every cycle |
| `_active_season_mode()` | Resolve current season | Every cycle |

### Mode Handler Methods

| Method | Purpose | Called |
|---|---|---|
| `_apply_standby(option, branch)` | Hand control to Sessy | Standby modes |
| `_set_grid_setpoint(watts)` | Set grid power target | Grid modes |
| `_set_battery_setpoint(watts)` | Set battery power | Battery modes |

### Setpoint Calculator Methods

| Method | Purpose | Formula |
|---|---|---|
| `_charge_setpoint(soc, target, window_h)` | Pre-peak charge power | `(target - soc)/100 * capacity / window_h * 1.5` |
| `_discharge_setpoint(soc, floor, window_h)` | Price-spike discharge | `(soc - floor)/100 * capacity / window_h` |
| `_cheap_charge_setpoint(soc, ceiling, window_h)` | Cheap charge | `max_power_w` (always max when charging) |
| `_evening_peak_excess_setpoint(soc, target, hours)` | Excess discharge | `(soc - target)/100 * capacity / hours` |

### Sensor Reader Methods

| Method | Purpose | Source |
|---|---|---|
| `_get_soc()` | Get current SOC | `soc_sensor` state |
| `_get_current_price()` | Get current raw price | `price_sensor` state or `energy_prices` attr |
| `_get_prices_dict()` | Get full price dict | `price_sensor` `energy_prices` attribute |
| `_tunable(default, entity_id)` | Get live or default value | entity state or default |

### Price Analysis Methods

| Method | Purpose | Algorithm |
|---|---|---|
| `_contiguous_price_hours(threshold, above)` | Count consecutive hours past threshold | Iterate forward from current hour |
| `_spread_window_h(threshold, above)` | Adaptive window with floor | `max(_contiguous..., min_window_h)` |
| `_max_price_in_window(start, end)` | Max price in hour range | Iterate, collect, return max |
| `_daily_min_price_hour_and_value()` | Find today's minimum | Iterate all 24 hours |

### Season Methods

| Method | Purpose | Logic |
|---|---|---|
| `_active_season_mode()` | Resolve current season | Check entity, then infer, then fallback |
| `_infer_season_from_price_minimum()` | Infer from price data | Daytime min → summer, night min → winter |
| `_seasonal_value(base, season, winter_override)` | Get seasonal value | Return winter override if season=winter, else base |

### Status Publishing Methods

| Method | Purpose | Parameters |
|---|---|---|
| `_publish_status(branch, **fields)` | Full context publish | All decision context |
| `_publish_branch(branch, **extra)` | Lightweight publish | Branch + extras |

### Callback Methods

| Method | Purpose | Trigger |
|---|---|---|
| `_on_input_change(entity, attr, old, new, kwargs)` | Schedule re-run | Live entity state change |
| `_rerun_now(kwargs)` | Execute immediate re-run | After debounce delay |

---

## Data Flow Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Home Assistant │────▶│ AppDaemon      │────▶│ SessyStrategy   │
│   (HA Core)      │     │ (App Container) │     │ (Python App)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ SOC sensor state      │                       │
         │ Price sensor state    │                       │
         │ energy_prices attr    │                       │
         │ entity states         │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│  App reads entities via HASS API:                              │
│  - self.get_state(entity_id) — get entity state                │
│  - self.get_state(entity_id, attribute="x") — get attribute    │
│  - self.call_service(domain, service, params) — call service   │
│  - self.set_state(entity_id, state, attrs) — update entity     │
└─────────────────────────────────────────────────────────────┘
         │                       │                       │
         │ Set strategy          │ Set grid/battery     │ Publish status
         │ Switch modes          │ setpoints            │ sensor
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Sessy          │◀────│   Sessy          │◀────│   Status        │
│   Integration    │     │   Entities      │     │   Sensor        │
│   (ha-sessy)    │     │   (select/number)│     │   (created)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Error Handling Strategy

### Critical Entity Check

```python
if not self._entity_exists(self.soc_sensor) or not self._entity_exists(self.price_sensor):
    self.log("Critical entities not available — skipping", level="WARNING")
    return
```

**Behavior:** Skip entire cycle, will retry next scheduled run.

### Service Call Wrapping

```python
try:
    self.call_service("select/select_option", ...)
    self.log(f"Strategy → {option}")
except Exception as e:
    self.log(f"Failed to apply strategy: {e}", level="WARNING")
```

**Behavior:** Log warning, continue execution, still publish status.

### Entity Existence Checks

All actuator methods check entity existence before making calls:

```python
if not self._entity_exists(self.strategy_select) or not self._entity_exists(self.grid_target):
    self.log("Entities not available", level="WARNING")
    return
```

---

## Memory and State Management

### Instance Variables (State)

| Variable | Type | Purpose | Persistence |
|---|---|---|---|
| `self._last_active_season` | str \| None | Track season changes for logging | Session only |
| `self._rerun_timer` | timer \| None | Debounce timer for live inputs | Session only |

**Note:** No persistent state between app restarts. All decisions are recomputed from scratch each cycle.

### No State Between Cycles

The strategy is **stateless** between cycles:
- No memory of previous decisions
- No accumulated state
- Each cycle reads current SOC, prices, mode
- Each cycle recomputes setpoints from scratch
- This makes it self-correcting: if SOC drifts, the next cycle adjusts

---

## Class Constants

| Constant | Value | Purpose |
|---|---|---|
| `_VALID_MODES` | `("optimized", "grid_setpoint", "battery_setpoint", "sessy_dynamic", "eco", "idle")` | Valid mode strings for normalization |

---

## File Structure

```
SessyStrategy_HA/
├── files/
│   └── sessy_strategy.py      # Main application
│   └── apps.yaml              # Example configuration
│   └── sessy_helpers.yaml     # Helper entity definitions
│
├── custom_components/
│   └── home_battery/           # Optional integration
│
└── tests/
    └── test_sessy_strategy.py # Unit tests
```

---

## Performance Characteristics

| Metric | Value | Notes |
|---|---|---|
| **Run frequency** | Every 5 minutes | Configurable via run_every |
| **Initial delay** | 30 seconds | Allow HA to initialize |
| **Re-run delay** | 2 seconds (default) | After live input change |
| **Max iterations** | 48 per run | Price data lookup |
| **Memory usage** | Minimal | No state between cycles |
| **CPU usage** | Low | Simple calculations |

---

## See Also

- [Configuration Reference](configuration/apps-yaml.md) — All tunable parameters
- [Entity Reference](entity-reference.md) — Entities used and created
- [Service Calls](service-calls.md) — Services called by the app
- [Algorithms](algorithms.md) — Calculation formulas and logic
- [Strategy Priority Chain](../../explanation/strategy-priority-chain.md) — Decision flow details
- [Setpoint Types Explained](../../explanation/setpoint-types-explained.md) — Control mode architecture
