# Setpoint Types Explained

## Overview

The SessyStrategy uses **two fundamentally different control modes** to manage your battery: **battery setpoint** and **grid setpoint**. Understanding the difference between these modes, when each is used, and their control philosophy is essential for understanding the strategy's behavior and for manual override operations.

---

## Control Philosophy

The SessyStrategy follows a **principled approach** to mode selection:

> **Use battery setpoint when we want to control the battery directly**
> **Use grid setpoint when we want to control grid interaction**

This distinction is reflected in which Sessy power strategy mode is selected:
- **`api` mode**: Battery setpoint (direct battery power control)
- **`nom` mode**: Grid setpoint (grid meter target control)

---

## Battery Setpoint (api mode)

### What It Means

The **battery setpoint** directly controls the **battery's charge/discharge power** in watts. This is the most direct form of battery control available.

**Entity:** `number.sessy_battery_*_power_setpoint`

**Value interpretation:**
- **Positive values**: Battery **discharges** (sends power to house/grid)
- **Negative values**: Battery **charges** (draws power from grid)
- **Zero**: Battery holds current SOC (neither charges nor discharges)

### When It's Used

The strategy uses battery setpoint (`api` mode) in the following priority branches:

| Priority | Name | Use Case | Setpoint Behavior |
|----------|------|----------|-------------------|
| 1 | Price-spike discharge | Avoid expensive imports | Positive value, discharge toward SOC floor |
| 2 | Cheap price charge | Capture cheap energy | Negative value, charge toward 100% |
| 3 | Pre-peak charge | Prepare for evening peak | Negative value, charge toward SOC target |

### Control Characteristics

**Pros:**
- [x] **Precise battery control**: Directly sets battery power to exact desired value
- [x] **Predictable behavior**: Battery behaves exactly as commanded
- [x] **Optimal for energy storage**: Ideal when the goal is to store/release specific amounts of energy
- [x] **Efficient power flow**: Can be tuned for maximum inverter efficiency

**Cons:**
- [ ] **Grid balance is automatic**: The grid will import or export whatever is needed to balance house load + battery power
- [ ] **Less direct grid control**: Cannot directly control grid import/export
- [ ] **May cause unexpected grid behavior**: If house load is high, battery discharge might not be enough, causing grid import

### Mathematical Control

The battery setpoint is calculated based on:

1. **Energy gap**: Difference between current SOC and target SOC
2. **Time window**: Hours available to make the transition
3. **Power limits**: Clamped at `max_power_w`

**General formula:**
```
power_w = (energy_gap_wh) / (window_h)
energy_gap_wh = (target_soc - current_soc) / 100 × capacity_wh
```

**For discharge (P1):**
```
available_wh = (soc - soc_floor) / 100 × capacity_wh
spread_w = available_wh / window_h
discharge_w = max(50, min(spread_w, max_power_w))
```

**For charge (P2, P3):**
```
gap_wh = (target_soc - soc) / 100 × capacity_wh
spread_w = gap_wh / window_h
charge_w = max(min_power_w, min(spread_w × 1.5, max_power_w))
```

### Example Scenarios

**Scenario 1: Price Spike Discharge**
```
SOC: 80%, soc_floor: 20%, capacity: 5000 Wh
Window: 2 hours
Available energy: (80-20)/100 × 5000 = 3000 Wh
Discharge power: 3000 / 2 = 1500 W
Setpoint: +1500 W (battery discharges at 1500W)
```

**Scenario 2: Pre-Peak Charge**
```
SOC: 60%, soc_target: 70%, capacity: 5000 Wh
Window: 2 hours
Energy gap: (70-60)/100 × 5000 = 500 Wh
Base power: 500 / 2 = 250 W
With 1.5× boost: 250 × 1.5 = 375 W
With min_power_w floor (66% of 2200 = 1452 W): 1452 W
Setpoint: -1452 W (battery charges at 1452W)
```

---

## Grid Setpoint (nom mode)

### What It Means

The **grid setpoint** controls the **power at the grid connection point** (meter) in watts. The battery responds automatically to maintain this target.

**Entity:** `number.sessy_*_grid_target`

**Value interpretation:**
- **Positive values**: **Import** from grid (house + battery consume more than PV generates)
- **Negative values**: **Export** to grid (house + battery generate more than they consume)
- **Zero**: **Net zero** at the meter (PV generation = house load + battery charging)

### When It's Used

The strategy uses grid setpoint (`nom` mode) in the following priority branches:

| Priority | Name | Use Case | Setpoint Behavior |
|----------|------|----------|-------------------|
| 4 | Evening peak excess | Discharge excess SOC | Negative value, export surplus |
| 5 | Default | Normal operation | Zero, absorb solar/block export |

Additionally, grid setpoint is used in **manual mode** when `grid_setpoint` mode is selected.

### Control Characteristics

**Pros:**
- [x] **Direct grid control**: Precisely controls import/export at the meter
- [x] **Battery handles the rest**: Battery automatically adjusts to achieve the grid target
- [x] **Simple mental model**: Think in terms of "what do I want at the meter"
- [x] **Good for export control**: Can precisely limit or block grid export

**Cons:**
- [ ] **Less precise battery control**: Battery power is determined by grid target, not directly controlled
- [ ] **Battery may work harder**: To achieve grid target, battery might charge/discharge more than expected
- [ ] **House load affects battery**: High house load means battery works harder to maintain grid target

### Mathematical Control

**Priority 4 (Evening Peak Excess):**
```
gap_wh = (soc - soc_target) / 100 × capacity_wh
spread_w = gap_wh / max(hours_remaining, 0.083)
discharge_w = max(50, min(spread_w, max_power_w))
Setpoint: -discharge_w (negative = export)
```

**Priority 5 (Default):**
```
Setpoint: 0 W (net zero at meter)
```

### Important Behavior: Battery Covers House Load

When using grid setpoint with a **negative value** (export target), the battery behavior is special:

```
Grid setpoint: -1000 W (export 1000W)
House load: 1500 W
Battery behavior: Battery must provide 1500W (house) + 1000W (export) = 2500W
```

**Key insight:** The battery **covers household load ON TOP OF** the export target. The grid never imports to meet the export target.

This means:
- High house load → battery works harder to maintain the export target
- The battery never pulls from grid to achieve an export target
- If battery cannot provide enough power, the export target simply isn't met

### Example Scenarios

**Scenario 1: Evening Peak Excess**
```
SOC: 95%, soc_target: 70%, capacity: 5000 Wh
Hours remaining in peak: 2 hours
Energy gap: (95-70)/100 × 5000 = 1250 Wh
Spread power: 1250 / 2 = 625 W
Setpoint: -625 W (export 625W from grid perspective)

With house load of 1000W:
- Battery provides: 1000W (house) + 625W (export) = 1625W
- Grid shows: -625W (export)
- House gets: 1000W from battery
```

**Scenario 2: Default Operation**
```
Setpoint: 0 W (net zero at meter)
House load: 500W
PV generation: 1500W

Power flow:
- House uses 500W from PV
- Remaining PV: 1000W → battery
- Grid: 0W (net)
- Battery charges at 1000W

If battery is full:
- House uses 500W from PV
- Remaining PV: 1000W → export (grid shows +1000W)
```

---

## Control Philosophy in Depth

### Why Different Modes for Different Priorities?

The choice of control mode reflects the **primary objective** of each priority:

| Priority | Objective | Mode | Why? |
|----------|-----------|------|------|
| 1, 2, 3 | **Battery energy management** | api | We care about battery SOC, not grid behavior |
| 4 | **Grid export management** | nom | We care about selling excess to grid |
| 5 | **Self-consumption maximization** | nom | We care about net zero at meter |

### Battery Setpoint for Energy Storage

Priorities 1-3 are fundamentally about **storing and releasing energy optimally**:
- P1: Discharge stored energy to avoid expensive imports
- P2: Store cheap energy for later use
- P3: Store energy before expensive peak

All of these require **precise control of battery power** to ensure the right amount of energy is stored or released over the right timeframe.

### Grid Setpoint for Grid Interaction

Priorities 4-5 are fundamentally about **grid interaction**:
- P4: Sell excess stored energy back to grid
- P5: Prevent exporting solar to grid (use it all locally)

These use grid setpoint because the **primary concern is what happens at the grid connection**, not the battery's internal state.

---

## Mode Switching

### Automatic Mode Switching

The strategy **automatically switches** between `api` and `nom` modes based on which priority is active:

```python
# In _set_battery_setpoint:
if current_strategy != "api":
    call_service("select/select_option", 
                entity_id=strategy_select, 
                option="api")
    log("Strategy → api (battery setpoint)")

# In _set_grid_setpoint:
if current_strategy != "nom":
    call_service("select/select_option", 
                entity_id=strategy_select, 
                option="nom")
    log("Strategy → nom (grid setpoint)")
```

**Key insight:** The strategy only switches modes when necessary, avoiding unnecessary service calls.

### Manual Mode Override

The strategy supports manual override modes via the `mode_select` entity:

| Mode | Description | Setpoint Entity | Behavior |
|------|-------------|-----------------|----------|
| `optimized` | Run full strategy | N/A | Automatic mode switching |
| `grid_setpoint` | Manual grid control | `setpoint_entity` | Grid setpoint, value from manual input |
| `battery_setpoint` | Manual battery control | `setpoint_entity` | Battery setpoint, value from manual input |
| `sessy_dynamic` | Use Sessy's own schedule | N/A | Hands control to Sessy |
| `eco` | Eco mode | N/A | Hands control to Sessy eco |
| `idle` | Idle mode | N/A | Parks the battery |

### When to Use Each Manual Mode

| Situation | Recommended Mode | Use Case |
|-----------|------------------|----------|
| Normal operation | `optimized` | Let strategy make all decisions |
| Force specific grid behavior | `grid_setpoint` | Set exact import/export target |
| Force specific battery behavior | `battery_setpoint` | Set exact charge/discharge power |
| Let Sessy handle it | `sessy_dynamic` | Use Sessy's built-in schedule |
| Minimal operation | `eco` | Use Sessy's eco mode |
| No operation | `idle` | Park battery, no charging/discharging |

---

## Diagram: Control Flow

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TD
    A[Strategy Decision] --> B{Priority 1-3?}
    B -->|Yes| C[Set api mode]
    C --> D[Set battery setpoint]
    B -->|No| E{Priority 4?}
    E -->|Yes| F[Set nom mode]
    F --> G[Set grid setpoint
      (negative = export)]
    E -->|No| H[Priority 5?]
    H -->|Yes| I[Set nom mode]
    I --> J[Set grid setpoint = 0W]
    H -->|No| K[Manual mode?]
    K -->|grid_setpoint| L[Set nom mode + manual grid target]
    K -->|battery_setpoint| M[Set api mode + manual battery target]
    K -->|other| N[Stand-down: idle/sessy_dynamic/eco]
```

---

## Mermaid Diagram: Conceptual Comparison

```mermaid
%%{init: {'theme': 'neutral'}}%%
xychart-beta
    title "Battery vs Grid Setpoint Response"
    x-axis ["Low Load", "Medium Load", "High Load"]
    y-axis "Power (W)" -2500 --> 2500
    
    %% Battery setpoint: fixed battery power
    line [1500, 1500, 1500]
    text "Battery setpoint: +1500W" at [0, 1600]
    
    %% Grid setpoint: battery adjusts to maintain grid target
    bar [0, 0, 0]
    text "Grid setpoint: 0W" at [0, 200]
    text "Grid setpoint: 0W" at [1, 200]
    text "Grid setpoint: 0W" at [2, 200]
```

---

## See Also

- [Strategy Priority Chain](../explanation/strategy-priority-chain.md) — Which priorities use which setpoint type
- [Price Basis: Raw vs Import](../explanation/price-basis-raw-vs-import.md) — Understanding the price calculations that drive decisions
- [Seasonal Operation](../explanation/seasonal-operation.md) — How seasons affect setpoint choices
- [Override Manual Mode](../how-to/override-manual-mode.md) — Using manual modes for specific situations
- [apps.yaml Configuration](../reference/configuration/apps-yaml.md) — All mode-related parameters
- [Architecture Reference](../reference/architecture.md) — Technical details of mode switching
