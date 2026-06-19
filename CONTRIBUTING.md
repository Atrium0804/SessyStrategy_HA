# Contributing Guidelines — SessyStrategy HA

Thank you for considering contributing! This guide covers **what to do** when contributing. For **how to write code**, see [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md).

---

## Quick Links

- 📋 **Process (this file)** — Contribution workflow and checklist
- 💻 **[CODING_PRINCIPLES.md](CODING_PRINCIPLES.md)** — How to write quality code
- 📖 **[README.md](README.md)** — Strategy explanation and full configuration reference
- 🤖 **[AGENTS.md](AGENTS.md)** — Agent routing for complex tasks

---

## Project Layout

```
SessyStrategy_HA/
├── files/
│   ├── sessy_strategy.py     # AppDaemon app — all strategy logic
│   ├── apps.yaml             # All tunables and entity IDs
│   ├── sessy_helpers.yaml    # Optional HA helper entities
│   └── appdaemon.example.yaml
├── tests/                    # pytest unit tests
│   └── test_sessy_strategy.py
├── README.md
├── requirements.txt
├── CODING_PRINCIPLES.md
└── CONTRIBUTING.md
```

---

## Checklist for Changes

### 1. Follow Coding Principles
   - ⚠️ **MANDATORY:** Read and follow [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md)
   - Write flat, explicit code — no unnecessary abstractions
   - Keep `update_strategy()` as a linear priority chain
   - Extract pure helper methods that are easy to unit-test

### 2. Strategy logic changes
   - New priority rules go above the default `grid_setpoint = 0W` branch
   - Add the new tunable to `apps.yaml` with a sensible default and a comment
   - Read new tunables in `initialize()` using `self.args.get("key", default)`
   - Log the decision and reason inside the new branch

### 3. Update `apps.yaml`
   - Add any new config keys with a descriptive inline comment
   - Group related keys under a comment header (see existing style)
   - Never hardcode values in the Python file that belong in `apps.yaml`

### 4. Update `requirements.txt`
   - Add new Python dependencies if needed
   - The AppDaemon runtime is provided by the HA add-on; only add packages needed for local linting or tests

### 5. Write unit tests
   - Tests live in `tests/test_sessy_strategy.py`
   - Test pure helper functions directly (no AppDaemon mock needed)
   - **Minimum requirements per change type:**
     - New helper function → happy path + edge case (e.g. SOC already at target)
     - Bug fix → test that reproduces the bug and verifies the fix
     - Changed behaviour → update existing tests to reflect new behaviour
     - New tunable → test that it is read correctly and affects output
   - Run before submitting: `pytest tests/ -v`

### 6. Update `README.md`
   - Add new tunables to the **Configuration reference** table
   - Update the **How the strategy works** section if behaviour changed
   - Add or update examples if the change affects operation in a visible way

### 7. Test and debug
   - Run all tests: `pytest tests/ -v`
   - Check the AppDaemon log after deploying to verify the new log lines appear as expected
   - Fix any issues before submitting

---

## Code Quality Standards

When writing code, follow [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md):

- ✅ **Flat and explicit** — no unnecessary abstractions
- ✅ **Linear priority flow** — `update_strategy` reads top-to-bottom
- ✅ **Small helpers** — extract pure functions for calculations
- ✅ **Config in `apps.yaml`** — no magic numbers in Python
- ✅ **Descriptive names** — clear but not verbose
- ✅ **Informative log messages** — log decision + reason every cycle
- ✅ **AppDaemon idioms** — `self.log()`, `self.get_state()`, `self.call_service()`
- ✅ **Testable helpers** — pure functions with no HA dependency where possible
- ✅ **Tests verify observable behaviour** — not implementation details

---

## Related Documentation

- [README.md](README.md) — Strategy explanation and configuration reference
- [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md) — Detailed coding standards with examples
- [AGENTS.md](AGENTS.md) — Agent routing for complex tasks
- [files/apps.yaml](files/apps.yaml) — All tunables and entity IDs

---

Please review this checklist before submitting a pull request. Thank you!

**Last updated:** 2026-06-19
