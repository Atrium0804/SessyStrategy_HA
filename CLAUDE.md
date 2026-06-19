# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SessyStrategy HA is an **AppDaemon 4** application for Home Assistant that optimizes a Sessy home battery system. It runs every 5 minutes and executes a 4-priority decision chain based on dynamic energy prices and battery state-of-charge (SOC).

**Runtime:** AppDaemon 4 add-on inside Home Assistant — there is no local dev server or build step. The only runtime dependency is `appdaemon>=4.4` (see `requirements.txt`).

## Deployment (not local dev)

Install by copying files to the HA instance:

```
files/sessy_strategy.py  →  /config/appdaemon/apps/sessy_strategy.py
files/apps.yaml          →  /config/appdaemon/apps/apps.yaml  (merge with existing)
files/sessy_helpers.yaml →  /config/packages/sessy_helpers.yaml  (optional, for UI)
```

Restart AppDaemon after any change to `sessy_strategy.py` or `apps.yaml`.

## Testing

**No test suite currently exists.** `tests/` is referenced in CONTRIBUTING.md but has not been created — this is a known high-priority gap (see COMPLIANCE_AUDIT.md). When writing tests, use `pytest` with mocked AppDaemon (`hass.Hass`) and HA entity state.

## Architecture

### Single-class design

`SessyStrategy(hass.Hass)` in `files/sessy_strategy.py` is the entire application:

- **`initialize()`** — reads `apps.yaml` config into `self.*` attributes, schedules `update_strategy()` to run every 5 minutes. No logic here.
- **`update_strategy(kwargs)`** — the sole decision entry point; runs each cycle as a linear if/elif priority chain.

### Decision priority chain (top wins, returns early)

1. **Price spike** — raw price > `price_discharge` → discharge toward SOC floor over 2 hours
2. **Cheap/negative price** — raw price < `price_charge` → charge toward 100% SOC over remaining cheap window
3. **Pre-peak charge** — in time window (16–18h) AND SOC < target AND evening peak beats current price by margin → charge toward SOC target
4. **Default** — grid setpoint = 0W (absorb solar, block export)

### Helper method categories

| Category | Methods |
|---|---|
| Setpoint calculators | `_charge_setpoint()`, `_discharge_setpoint()`, `_cheap_charge_setpoint()` |
| Sensor readers | `_get_soc()`, `_get_current_price()`, `_count_cheap_hours()`, `_max_price_in_window()`, `_daily_min_price_hour_and_value()` |
| Actuators | `_set_grid_setpoint(watts)`, `_set_battery_setpoint(watts)` |
| Seasonal logic | `_active_season_mode()`, `_infer_season_from_price_minimum()`, `_seasonal_value()` |
| Status | `_publish_status()` — writes all current state to `sensor.sessy_strategy_status` |

### Configuration

All tunables live in `files/apps.yaml`. **No magic numbers in Python** — if a value might need tuning, it belongs in `apps.yaml`. Key groups:

- Hardware: `capacity_wh`, `max_power_w`, `c_rate_cap`
- SOC targets: `soc_target` (90%), `soc_floor` (20%), `cheap_soc_target` (100%)
- Price thresholds: `price_discharge` (0.39), `price_charge` (-0.10), `min_arbitrage_margin` (0.05)
- Time windows: `prepeak_start/end`, `evening_peak_start/end`, winter variants
- Season auto-detect: `season_day_start/end` (8–18h)

Optional `sessy_helpers.yaml` adds `input_number` / `input_select` HA helpers for live runtime tuning without restarting AppDaemon.

## Coding Principles (enforced)

Full detail in `CODING_PRINCIPLES.md`. Key rules:

- **Flat, explicit code** over abstractions. No factory classes, dispatch tables, or deep nesting.
- **`update_strategy()` stays linear** — readable top-to-bottom as if/elif branches.
- **`initialize()` only reads config and schedules** — zero strategy logic.
- **Extract shared logic** into named helper methods before duplicating.
- **All HA entity reads/writes** go through named helper calls; don't store HA state in instance variables between cycles.
- **No magic numbers** — all tunables in `apps.yaml`.
- **Comments explain *why*, not what** — if you need a comment to explain how the code works, simplify the code.

## Known Gaps (COMPLIANCE_AUDIT.md, 2026-06-19)

| Priority | Issue | Fix |
|---|---|---|
| 🔴 High | No test suite | Create `tests/test_sessy_strategy.py` with pytest + mocked `hass.Hass` |
| 🟡 Medium | Hardcoded `max(50, ...)` in three setpoint methods | Extract `min_setpoint_w` to `apps.yaml` |
| 🟢 Low | Some direct `get_state()` calls not routed through helpers | Wrap in named helper methods |
