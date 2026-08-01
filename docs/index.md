---
title: SessyStrategy HA Documentation
description: Complete documentation for SessyStrategy HA using Diátaxis methodology
author: SessyStrategy Team
created: 2026-08-01
last_updated: 2026-08-01
---

# 📚 SessyStrategy HA Documentation

**Smart battery charging strategy for Home Assistant + Sessy**

> *Following the [Diátaxis Documentation Framework](https://diataxis.fr/)*

---

## 🎯 Welcome

SessyStrategy HA is an intelligent battery management strategy that optimizes your energy usage by making smart decisions about when to charge and discharge your battery based on real-time energy prices, solar production, and your usage patterns.

This documentation is organized using the **Diátaxis methodology**, which categorizes information into four distinct types based on user needs:

---

## 🗺️ Documentation Navigation

### 📚 Tutorials *(Learning-oriented)*
*Follow along step-by-step to learn how to use SessyStrategy HA*

| Tutorial | Description | Time | Difficulty |
|----------|-------------|------|------------|
| [Getting Started](tutorials/getting-started.md) | Complete setup from scratch | 30-45 min | Beginner |
| [First Day Operation](tutorials/first-day-operation.md) | What to expect on day one | 15 min | Beginner |
| [Dashboard Setup](tutorials/dashboard-setup.md) | Create visual dashboards | 20-30 min | Intermediate |

**🎯 Start here if you're new to SessyStrategy HA**

---

### 🛠️ How-to Guides *(Problem-oriented)*
*Solve specific problems with practical, actionable solutions*

| Guide | Problem Solved | Time |
|-------|----------------|------|
| [Tune Price Thresholds](how-to/tune-price-thresholds.md) | Adjust charge/discharge price points | 10-15 min |
| [Debug Strategy Decisions](how-to/debug-strategy-decisions.md) | Understand why the strategy made a decision | 10-20 min |
| [Configure Seasonal Mode](how-to/configure-seasonal-mode.md) | Set up winter/summer behavior | 10 min |
| [Override Manual Mode](how-to/override-manual-mode.md) | Force a specific setpoint | 5-10 min |
| [Add Live Tuning Helpers](how-to/add-live-tuning-helpers.md) | Adjust settings without restarting | 15 min |
| [Migrate from Older Version](how-to/migrate-from-older-version.md) | Upgrade from previous versions | 10-15 min |

**🔧 Use these when you have a specific problem to solve**

---

### 💡 Explanations *(Understanding-oriented)*
*Learn the concepts and theory behind how SessyStrategy HA works*

| Explanation | Concept | Level |
|-------------|---------|-------|
| [Strategy Priority Chain](explanation/strategy-priority-chain.md) | How decisions are made | Intermediate |
| [Price Basis: Raw vs Import](explanation/price-basis-raw-vs-import.md) | Understanding price calculations | Beginner |
| [Adaptive Spread Windows](explanation/adaptive-spread-windows.md) | Power distribution over time | Intermediate |
| [Setpoint Types Explained](explanation/setpoint-types-explained.md) | Battery vs Grid setpoints | Intermediate |
| [Seasonal Operation](explanation/seasonal-operation.md) | Winter vs summer modes | Beginner |
| [Arbitrage Margin](explanation/arbitrage-margin.md) | Profitability calculations | Advanced |

**💡 Read these to understand the "why" behind the "how"**

---

### 📖 Reference *(Information-oriented)*
*Look up technical details and specifications*

| Document | Type | Description |
|----------|------|-------------|
| [apps.yaml Configuration](reference/configuration/apps-yaml.md) | Configuration | All tunable parameters |
| [Entity Reference](reference/entity-reference.md) | Entities | Required, optional, and created entities |
| [Live Tuning Entities](reference/live-tuning-entities.md) | Entities | Runtime-adjustable settings |
| [Status Sensor Attributes](reference/status-sensor-attributes.md) | Sensor | Complete attribute list |
| [Service Calls](reference/service-calls.md) | API | Available service methods |
| [Architecture](reference/architecture.md) | Architecture | AppDaemon lifecycle and callbacks |
| [Algorithms](reference/algorithms.md) | Algorithms | Formulas and calculations |

**📚 Consult these for technical details and specifications**

---

## 🚀 Quick Start Guide

New to SessyStrategy HA? Follow these steps:

### 1️⃣ Install
Copy the strategy file to your AppDaemon apps directory:
```bash
cp files/sessy_strategy.py /config/appdaemon/apps/
```

### 2️⃣ Configure
Add a basic configuration to your `apps.yaml`:
```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  soc_sensor: sensor.your_battery_soc
  price_sensor: sensor.your_energy_price
```

### 3️⃣ Run
Restart AppDaemon and check for the status sensor:
```
sensor.sessy_strategy_status
```

### 4️⃣ Learn
Continue with the full [Getting Started Tutorial](tutorials/getting-started.md)

---

## 📊 Documentation Statistics

| Category | Documents | Purpose |
|----------|-----------|---------|
| Tutorials | 3 | Learning-oriented |
| How-to | 6 | Problem-oriented |
| Explanations | 6 | Understanding-oriented |
| Reference | 7 | Information-oriented |
| **Total** | **22** | - |

---

## 🎨 Documentation Structure

```
docs/
├── 📚 tutorials/
│   ├── getting-started.md
│   ├── first-day-operation.md
│   └── dashboard-setup.md
│
├── 🛠️ how-to/
│   ├── configure-seasonal-mode.md
│   ├── tune-price-thresholds.md
│   ├── override-manual-mode.md
│   ├── add-live-tuning-helpers.md
│   ├── debug-strategy-decisions.md
│   └── migrate-from-older-version.md
│
├── 💡 explanation/
│   ├── strategy-priority-chain.md
│   ├── price-basis-raw-vs-import.md
│   ├── adaptive-spread-windows.md
│   ├── setpoint-types-explained.md
│   ├── seasonal-operation.md
│   └── arbitrage-margin.md
│
└── 📖 reference/
    ├── configuration/
    │   └── apps-yaml.md
    ├── entity-reference.md
    ├── live-tuning-entities.md
    ├── status-sensor-attributes.md
    ├── service-calls.md
    ├── architecture.md
    └── algorithms.md
```

---

## 🤝 Contributing to Documentation

Found an error or want to improve the documentation? 

1. **Report an issue:** [Open a GitHub issue](https://github.com/your-repo/issues)
2. **Submit a PR:** Fork the repo, make your changes, and submit a pull request
3. **Follow the templates:** Use the templates in [`docs/_templates/`](_templates/) for new documents

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.

---

## 📄 License

This documentation is licensed under [MIT License](../LICENSE).

---

## 🔗 External Links

- [Sessy Integration](https://github.com/andrew-codechimp/Sessy)
- [AppDaemon Documentation](https://appdaemon.readthedocs.io)
- [Home Assistant](https://www.home-assistant.io)
- [Diátaxis Framework](https://diataxis.fr/)

---

## 📞 Support

- **Documentation Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **General Questions:** [GitHub Discussions](https://github.com/your-repo/discussions)
- **Community:** [Join the conversation](link-to-community)

---

## 📝 Recent Updates

| Date | Document | Change | Author |
|------|----------|--------|--------|
| 2026-08-01 | Documentation Plan | Phase 1: Infrastructure Setup Complete | System |

---

*Documentation last updated: 2026-08-01*
*Documentation structure based on [Diátaxis Methodology](https://diataxis.fr/)*
