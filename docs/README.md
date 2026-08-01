# SessyStrategy HA Documentation

**Complete Documentation for Smart Battery Charging Strategy**

> *Organized using the [Diátaxis Documentation Framework](https://diataxis.fr/)*

---

## Welcome to SessyStrategy HA Documentation

**Status: All Phases Complete (1-6)**

This documentation system provides comprehensive guides for SessyStrategy HA. All phases are now complete with 24 documents across 4 categories following the Diátaxis methodology.

This system provides everything you need to understand, install, configure, and optimize SessyStrategy HA for your home battery system.

---

## Documentation Navigation

Our documentation is organized into **four categories** following the Diátaxis methodology, each serving a distinct user need:

---

### Tutorials *(Learning-Oriented)*

**Follow along step-by-step** to learn how to use SessyStrategy HA from scratch.

| Tutorial | Description | Time | Difficulty |
|----------|-------------|------|------------|
| [Getting Started](tutorials/getting-started.md) | Complete installation and setup from scratch | 30-45 min | Beginner |
| [First Day Operation](tutorials/first-day-operation.md) | Understand what to expect during your first day | 15 min | Beginner |
| [Dashboard Setup](tutorials/dashboard-setup.md) | Create visual dashboards with ApexCharts | 20-30 min | Intermediate |

Start here if you're new to SessyStrategy HA.

---

### How-to Guides *(Problem-Oriented)*

**Solve specific problems** with practical, actionable solutions.

| Guide | Problem Solved | Time | Difficulty |
|-------|----------------|------|------------|
| [Tune Price Thresholds](how-to/tune-price-thresholds.md) | Adjust charge/discharge price points for your situation | 10-15 min | Intermediate |
| [Debug Strategy Decisions](how-to/debug-strategy-decisions.md) | Understand why the strategy made a specific decision | 10-20 min | Intermediate |
| [Configure Seasonal Mode](how-to/configure-seasonal-mode.md) | Set up optimal winter/summer behavior | 10 min | Beginner |
| [Override Manual Mode](how-to/override-manual-mode.md) | Force a specific setpoint when needed | 5-10 min | Beginner |
| [Add Live Tuning Helpers](how-to/add-live-tuning-helpers.md) | Adjust settings from dashboard without restart | 15 min | Intermediate |
| [Migrate from Older Version](how-to/migrate-from-older-version.md) | Upgrade from previous versions | 10-15 min | Beginner |

Use these when you have a specific problem to solve.

---

### Explanations *(Understanding-Oriented)*

**Learn the concepts and theory** behind how SessyStrategy HA works.

| Explanation | Concept | Level | Audience |
|-------------|---------|-------|----------|
| [Strategy Priority Chain](explanation/strategy-priority-chain.md) | How the decision-making priority system works | Intermediate | All users |
| [Price Basis: Raw vs Import](explanation/price-basis-raw-vs-import.md) | Understanding price calculations and surcharges | Beginner | Essential |
| [Adaptive Spread Windows](explanation/adaptive-spread-windows.md) | How power is distributed over time | Intermediate | Advanced users |
| [Setpoint Types Explained](explanation/setpoint-types-explained.md) | Battery vs grid setpoints and their uses | Intermediate | All users |
| [Seasonal Operation](explanation/seasonal-operation.md) | Winter vs summer modes and automatic detection | Beginner | All users |
| [Arbitrage Margin](explanation/arbitrage-margin.md) | Profitability calculations and break-even analysis | Advanced | Power users |

Read these to understand the "why" behind the "how".

---

### Reference *(Information-Oriented)*

**Look up technical details and specifications** when you need precise information.

| Document | Type | Description | Audience |
|----------|------|-------------|----------|
| [apps.yaml Configuration](reference/configuration/apps-yaml.md) | Configuration | All tunable parameters and options | All users |
| [Entity Reference](reference/entity-reference.md) | Entities | Complete list of required, optional, and created entities | All users |
| [Live Tuning Entities](reference/live-tuning-entities.md) | Entities | Runtime-adjustable settings and helpers | Advanced users |
| [Status Sensor Attributes](reference/status-sensor-attributes.md) | Sensor | Complete attribute list and descriptions | All users |
| [Service Calls](reference/service-calls.md) | API | Services used by the strategy | Advanced users |
| [Architecture](reference/architecture.md) | Architecture | AppDaemon lifecycle, callbacks, and class structure | Developers |
| [Algorithms](reference/algorithms.md) | Algorithms | Formulas, calculations, and edge cases | Advanced users |

Consult these for technical details and specifications.

---

## Getting Started Quick Path

New to SessyStrategy HA? Follow this path:

```
Step 1: Tutorial: Getting Started
    ├─ Install AppDaemon
    ├─ Copy strategy files
    ├─ Configure apps.yaml
    └─ Verify installation
    
Step 2: Tutorial: First Day Operation
    ├─ Understand morning behavior
    ├─ Learn pre-peak charging
    ├─ See evening peak discharge
    └─ Monitor night charging
    
Step 3: Explanation: Strategy Priority Chain
    ├─ Learn P1-P5 priorities
    ├─ Understand decision flow
    └─ See why this order works
    
Step 4: Reference: apps.yaml Configuration
    ├─ Review all tunables
    ├─ Set optimal values
    └─ Configure for your system
    
Step 5: Tutorial: Dashboard Setup
    ├─ Create visual monitoring
    └─ Add charts and gauges
```

---

## Documentation Statistics

| Category | Documents | Total Pages | Purpose | Completion |
|----------|-----------|-------------|---------|------------|
| Tutorials | 3 | ~50 | Learning-oriented | [x] Complete |
| How-to | 6 | ~80 | Problem-oriented | [x] Complete |
| Explanation | 6 | ~60 | Understanding-oriented | [x] Complete |
| Reference | 7 | ~70 | Information-oriented | [x] Complete |
| **Total** | **22** | **~260** | | **All Phases Complete** |

---

## Documentation Structure

```
docs/
├── README.md                          # This file - documentation overview
├── index.md                           # Main documentation landing page
├── .gitignore                         # Documentation ignore rules
├── _sidebar.yml                       # Sidebar configuration for static sites
│
├── tutorials/
│   ├── getting-started.md          # Step-by-step installation guide
│   ├── first-day-operation.md      # First day expectations and monitoring
│   └── dashboard-setup.md          # Dashboard creation with ApexCharts
│
├── how-to/
│   ├── configure-seasonal-mode.md  # Seasonal mode setup guide
│   ├── tune-price-thresholds.md    # Price threshold adjustment
│   ├── override-manual-mode.md     # Manual control override
│   ├── add-live-tuning-helpers.md  # Live parameter tuning
│   ├── debug-strategy-decisions.md # Debugging and troubleshooting
│   └── migrate-from-older-version.md # Version migration guide
│
├── explanation/
│   ├── strategy-priority-chain.md  # Priority system deep dive
│   ├── price-basis-raw-vs-import.md # Price calculation explanation
│   ├── adaptive-spread-windows.md  # Spread algorithm details
│   ├── setpoint-types-explained.md  # Setpoint type comparison
│   ├── seasonal-operation.md       # Seasonal behavior logic
│   └── arbitrage-margin.md          # Profitability analysis
│
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

---

## Documentation Quality Standards

Our documentation follows these quality criteria:

### All Documents Include
- [x] **Clear purpose and audience** in frontmatter
- [x] **Prerequisites** listed upfront
- [x] **Related documentation** cross-links
- [x] **Practical examples** with real-world scenarios
- [x] **Troubleshooting** sections for common issues
- [x] **Verification checklists** to confirm success
- [x] **Version metadata** (creation and update dates)

### Consistent Formatting
- [x] **Markdown standards** followed throughout
- [x] **Code blocks** with proper syntax highlighting
- [x] **Tables** for structured data presentation
- [x] **Mermaid diagrams** for complex concepts

### Navigation and Discovery
- [x] **Cross-links** between related documents
- [x] **Breadcrumb navigation** within categories
- [x] **Table of contents** at category level
- [x] **Search-friendly** structure and titles

---

## Contributing to Documentation

We welcome contributions to improve our documentation!

### How to Contribute

1. **Report Documentation Issues:**
   - Found an error? [Open a GitHub issue](https://github.com/your-repo/issues)
   - Suggest improvements via pull requests

2. **Add New Documentation:**
   - Use the templates in [`_templates/`](_templates/) for consistency
   - Follow the Diátaxis methodology
   - Add cross-links to related documents

3. **Improve Existing Docs:**
   - Fix typos and grammatical errors
   - Update outdated information
   - Add missing examples or use cases

### Documentation Templates

We provide templates for each document type:
- [Tutorial Template](_templates/tutorial-template.md)
- [How-to Template](_templates/how-to-template.md)
- [Explanation Template](_templates/explanation-template.md)
- [Reference Template](_templates/reference-template.md)

---

## Documentation Update History

| Date | Change | Author | Version |
|------|--------|--------|---------|
| 2026-08-01 | Phase 1: Infrastructure setup complete | System | 1.0 |
| 2026-08-01 | Phase 2: Reference documentation complete | System | 1.0 |
| 2026-08-01 | Phase 3: Explanation documentation complete | System | 1.0 |
| 2026-08-01 | Phase 4: How-to guides complete | System | 1.0 |
| 2026-08-01 | Phase 5: Tutorials complete | System | 1.0 |
| 2026-08-01 | Phase 6: Polish and finalization | System | 1.0 |

---

## External Resources

### Home Assistant and AppDaemon
- [Home Assistant Documentation](https://www.home-assistant.io/docs/)
- [AppDaemon Documentation](https://appdaemon.readthedocs.io)
- [AppDaemon GitHub](https://github.com/AppDaemon/appdaemon)

### Sessy Integration
- [Sessy Integration GitHub](https://github.com/andrew-codechimp/Sessy)
- [Sessy Documentation](https://github.com/andrew-codechimp/Sessy/wiki)

### Methodology
- [Diátaxis Framework](https://diataxis.fr/) - Our documentation methodology
- [Diátaxis GitHub](https://github.com/diataxis/diataxis.fr)

---

## Support

- **Documentation Questions:** [GitHub Discussions](https://github.com/your-repo/discussions)
- **Bug Reports:** [GitHub Issues](https://github.com/your-repo/issues)
- **Feature Requests:** [GitHub Issues](https://github.com/your-repo/issues)

---

## License

All documentation is licensed under the [MIT License](../LICENSE), same as the project code.

---

*Documentation created and maintained by the SessyStrategy HA team*
*Methodology: [Diátaxis Framework](https://diataxis.fr/)*
*Last updated: 2026-08-01 | Version: 1.0*