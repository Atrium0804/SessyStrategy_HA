# SessyStrategy HA

**Smart battery charging strategy for Home Assistant + Sessy**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![AppDaemon](https://img.shields.io/badge/AppDaemon-4.x-green.svg)](https://appdaemon.readthedocs.io)

---

## 📚 Documentation

| Category | Purpose | Documents |
|----------|---------|-----------|
| **Tutorials** | *Learning-oriented* — Follow along step-by-step | [Getting Started](docs/tutorials/getting-started.md) • [First Day](docs/tutorials/first-day-operation.md) • [Dashboard Setup](docs/tutorials/dashboard-setup.md) |
| **How-to** | *Problem-oriented* — Solve specific problems | [Set Up Boiler Strategy](docs/how-to/setup-boiler-strategy.md) • [Tune Thresholds](docs/how-to/tune-price-thresholds.md) • [Debug Decisions](docs/how-to/debug-strategy-decisions.md) • [Manual Override](docs/how-to/override-manual-mode.md) • [Live Tuning](docs/how-to/add-live-tuning-helpers.md) • [Migration Guide](docs/how-to/migrate-from-older-version.md) |
| **Explanation** | *Understanding-oriented* — Learn the concepts | [Priority Chain](docs/explanation/strategy-priority-chain.md) • [Price Basis](docs/explanation/price-basis-raw-vs-import.md) • [Spread Windows](docs/explanation/adaptive-spread-windows.md) • [Setpoint Types](docs/explanation/setpoint-types-explained.md) • [Arbitrage Margin](docs/explanation/arbitrage-margin.md) • [Boiler Strategy Priority Chain](docs/explanation/boiler-strategy-priority-chain.md) |
| **Reference** | *Information-oriented* — Look up technical details | [apps.yaml Config](docs/reference/configuration/apps-yaml.md) • [Boiler Strategy Config](docs/reference/configuration/boiler-strategy-config.md) • [Entity Reference](docs/reference/entity-reference.md) • [Live Entities](docs/reference/live-tuning-entities.md) • [Status Attributes](docs/reference/status-sensor-attributes.md) • [Service Calls](docs/reference/service-calls.md) • [Architecture](docs/reference/architecture.md) • [Algorithms](docs/reference/algorithms.md) |

---

## ⚡ Quick Start

New to SessyStrategy HA? Get started in minutes:

1. **Install**: Copy `files/sessy_strategy.py` to your AppDaemon apps directory
2. **Configure**: Add configuration to `apps.yaml` (see [Configuration Reference](docs/reference/configuration/apps-yaml.md))
3. **Run**: Restart AppDaemon
4. **Verify**: Check `sensor.sessy_strategy_status`

👉 **[Full Getting Started Guide](docs/tutorials/getting-started.md)**

---

## 🎯 What is SessyStrategy HA?

SessyStrategy HA is an intelligent AppDaemon-based charging strategy for the [Sessy home battery integration](https://github.com/andrew-codechimp/Sessy). It automatically optimizes your battery usage to:

- **Minimize solar export** - Store solar energy for later use instead of exporting to the grid
- **Avoid expensive grid imports** - Discharge stored energy during price spikes
- **Capture value during extreme price events** - Automatically respond to high and negative prices
- **Maximize self-consumption** - Use your own generated energy instead of importing from the grid

The strategy uses a **priority chain** to make decisions every 5 minutes based on real-time energy prices, battery state of charge (SOC), and configurable thresholds.

---

## 🏗️ Architecture Overview

```
SessyStrategy HA runs as an AppDaemon application:
├── Reads: SOC sensor, energy price sensor, mode selectors
├── Decides: Using priority chain (P1-P5) every 5 minutes
├── Controls: Battery setpoint (api mode) or grid target (nom mode)
└── Publishes: Status sensor with all current values and active branch
```

**Key Features:**
- ✅ **Adaptive spread windows** - Spreads charge/discharge over optimal time periods
- ✅ **Live tuning** - Adjust thresholds without restarting AppDaemon
- ✅ **Priority-based decisions** - Clear, logical decision making
- ✅ **Comprehensive logging** - Detailed logs for debugging

---

## 📊 Strategy Priority Chain

The strategy evaluates conditions in this order (first match wins):

| Priority | Condition | Action | Purpose |
|----------|-----------|--------|---------|
| **P1** | Price > discharge threshold | Battery setpoint (discharge) | Avoid expensive imports |
| **P2** | Price < charge threshold | Battery setpoint (charge) | Capture cheap/negative price energy |
| **P3** | Current hour among the N cheapest of the shared 24h price window + a later hour beats now by margin | Battery setpoint (charge) | Fill at the daily lows |
| **P4** | Afternoon window + evening peak beats now by margin | Battery setpoint (charge) | Prepare for evening peak |
| **P5** | Evening peak + excess SOC | Grid setpoint (export) | Sell surplus energy |
| **P6** | Morning window + excess SOC | Grid setpoint (export) | Sell the reserved morning energy |
| **P7** | Default | Grid setpoint 0W | Absorb solar, block export |

👉 **[Learn more about the Priority Chain](docs/explanation/strategy-priority-chain.md)**

---

## 🎛️ Configuration

SessyStrategy is configured via `apps.yaml` with sensible defaults:

**Required Configuration:**
```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  # Map to your entities
  soc_sensor: sensor.your_battery_soc
  price_sensor: sensor.your_energy_price
  strategy_select: select.your_power_strategy
  grid_target: number.your_grid_target
  battery_setpoint: number.your_battery_setpoint
```

**Key Tunables:**
- `price_discharge`: Raw price above which to discharge (default: 0.39 €/kWh)
- `price_charge`: Raw price below which to charge (default: -0.10 €/kWh)
- `target_afternoon_charging`: Target SOC before evening peak (default: 70%)
- `soc_floor`: Minimum SOC floor (default: 20%)

👉 [Full Configuration Reference](docs/reference/configuration/apps-yaml.md)

---

## � Boiler Strategy (add-on)

A companion AppDaemon app, `files/boiler_strategy.py` (config in `apps.yaml` under `boiler_strategy`), drives an Ariston hybrid boiler from a user-selected strategy mode plus weekly legionella prevention. See the full documentation for configuration and behavior details.

| Priority | Condition | Action |
|----------|-----------|--------|
| **P1** | Boiler hasn't reached `legionella_temp` in `legionella_boost_days` | Force mode `boost`, unless the user explicitly selected `off` |
| **P2** | `mode_select` is `off` / `heatpump` / `hybrid` / `boost` | Force that boiler mode directly — always takes effect |
| **P3** | Boiler hasn't reached `legionella_temp` in `legionella_hybrid_days` and the selected price strategy is in its cheap period | Force mode `hybrid` |
| **P4** | `mode_select` is `market_price_threshold` | Run the heat pump when the current price ≤ `market_price_threshold`; stay `off` otherwise |
| **P5** | `mode_select` is `cheapest_hours` (default) | Run the heat pump during the N cheapest hours (`cheapest_hours_count`) of the 24h price window from `cheapest_window_start_h` (default 02:00 → 02:00, shared with the battery); stay `off` otherwise |

The user mode input is an `input_select` (`mode_select`, provided by the boiler package as `input_select.boiler_strategy_mode`) with options `off`, `heatpump`, `hybrid`, `boost`, `market_price_threshold`, and `cheapest_hours` (default). The retired `economic` mode is gone: an unset mode or a leftover `economic` selection runs as `cheapest_hours`, and the app switches the `input_select` to `cheapest_hours` (WARNING in the log) — remove `economic` from the helper's options. Prices come from `price_forecast_sensor` (the Sessy `energy_prices` dict, read by `cheapest_hours.py` like the battery; the Frank Energie format is no longer supported). The threshold strategy uses the current local hour's price from that data and falls back to `current_price_sensor` only when it has no price for now; leave `current_price_attribute` empty when the price is the sensor state. The app writes decisions to the logical `select.boiler_mode` actuator, which in turn pushes the Ariston integration's own `max_temp` whenever a temperature needs to be set (there is no separate user-controllable setpoint). The app only writes `select.boiler_mode` when the decision changes, so `boost` is started once per selection: the package switches the Ariston to IMEMORY, raises the setpoint to `max_temp` (GREEN caps it at 53 °C), then starts BOOST, and retries at most once if the boost resistor (boiler power ≥ 1000 W) isn't running while the water is still below the setpoint — repeated restarts wear the heat pump. The last-reached legionella timestamp is tracked in an `input_datetime` helper (`legionella_last_ok_entity`) that the app stamps itself.

In `cheapest_hours` mode, `sensor.boiler_strategy_status` publishes the numeric
`cheapest_hours_price_threshold`: the highest average hourly market price among
the selected N hours. `cheapest_hours_window_start` and `cheapest_hours_window_end`
are ISO timestamps delimiting the configured 24h window, so a chart can draw one
threshold line only within that window instead of splitting price bars by color.
The threshold is `null` without a selection; all three attributes are `null` in
other modes. The threshold remains available during legionella overrides.
Equal prices can put more than N hours on or below the line; actual selection
still uses rank with earlier hours winning ties. Quarter-hour prices are averaged
per hour, so individual slots need not fall below the hourly threshold.
See [Status Sensor Attributes](docs/reference/status-sensor-attributes.md#boiler-cheapest-hours-threshold)
for the chart example.

See:
- [Boiler Strategy Configuration Reference](docs/reference/configuration/boiler-strategy-config.md)
- [Boiler Strategy Priority Chain Explained](docs/explanation/boiler-strategy-priority-chain.md)

---

## �🔧 Common Tasks

| Task | Guide |
|------|-------|
| Install and setup | [Getting Started](docs/tutorials/getting-started.md) |
| Understand first day | [First Day Operation](docs/tutorials/first-day-operation.md) |
| Create a dashboard | [Dashboard Setup](docs/tutorials/dashboard-setup.md) |
| Tune price thresholds | [Tune Thresholds](docs/how-to/tune-price-thresholds.md) |
| Debug strategy decisions | [Debug Decisions](docs/how-to/debug-strategy-decisions.md) |

---

## 📖 Documentation Structure

**All documentation is complete across all 4 Diátaxis categories:**
```
docs/
├── tutorials/
│   ├── getting-started.md          # Complete setup guide
│   ├── first-day-operation.md      # What to expect on day one
│   └── dashboard-setup.md          # Dashboard creation guide
├── how-to/
│   ├── tune-price-thresholds.md    # Price threshold adjustment
│   ├── override-manual-mode.md     # Manual control override
│   ├── add-live-tuning-helpers.md  # Live parameter tuning
│   ├── debug-strategy-decisions.md # Debugging and troubleshooting
│   └── migrate-from-older-version.md # Version migration guide
├── explanation/
│   ├── strategy-priority-chain.md  # Priority system deep dive
│   ├── price-basis-raw-vs-import.md # Price calculation explanation
│   ├── adaptive-spread-windows.md  # Spread algorithm details
│   ├── setpoint-types-explained.md  # Setpoint type comparison
│   └── arbitrage-margin.md          # Profitability analysis
└── reference/
    ├── configuration/
    │   └── apps-yaml.md              # Complete configuration reference
    ├── entity-reference.md          # Entity catalog
    ├── live-tuning-entities.md      # Live tuning entity reference
    ├── status-sensor-attributes.md  # Status sensor attribute list
    ├── service-calls.md             # Service call documentation
    ├── architecture.md               # Code architecture overview
    └── algorithms.md                # Algorithmic formulas and calculations
```

*All 24 documents are complete. See [DOCUMENTATION_PLAN.md](DOCUMENTATION_PLAN.md) for the full implementation details.*

---

## 🤝 Contributing

We welcome contributions to SessyStrategy HA! Please see:

- **[Contribution Guidelines](CONTRIBUTING.md)** - How to contribute code and documentation
- **[Coding Principles](CODING_PRINCIPLES.md)** - Development standards and best practices
- **[Testing Guide](TESTING.md)** - How to run and write tests

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🔗 Useful Links

- [Sessy Integration](https://github.com/andrew-codechimp/Sessy) - The underlying Sessy integration
- [AppDaemon Documentation](https://appdaemon.readthedocs.io) - AppDaemon framework documentation
- [Home Assistant](https://www.home-assistant.io) - Home automation platform
- [Diátaxis Framework](https://diataxis.fr/) - Documentation methodology used

---

## 📞 Support & Community

- **Documentation Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **General Questions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Bug Reports**: [GitHub Issues](https://github.com/your-repo/issues)
- **Feature Requests**: [GitHub Issues](https://github.com/your-repo/issues)

---

*Project maintained with love by the SessyStrategy HA team*
*Last updated: 2026-08-01* | *Documentation: [Diátaxis Methodology](https://diataxis.fr/)*