# Agents — SessyStrategy HA

This file defines agent routing rules for complex, multi-step tasks.

## Agent Routing Rules

### 1. `Explore` — Codebase Exploration & Research

**Use when:**
- Understanding how a strategy decision is implemented across the code
- Tracing how a config key flows from `apps.yaml` into `sessy_strategy.py`
- Answering questions that require reading multiple files at once
- Auditing test coverage or checking which helpers are untested

**Examples:**
- "Where is `price_discharge` used in the strategy logic?"
- "How does season detection work end-to-end?"
- "Which helper functions have no tests?"

**Thoroughness hint:** `quick` for targeted lookups, `medium` for feature understanding, `thorough` for audits.

---

### 2. Default Agent — Code Changes

**Use when:**
- Adding a new priority rule or strategy condition
- Changing a tunable or adding a new `apps.yaml` parameter
- Fixing a bug in `sessy_strategy.py` or a helper
- Writing or updating tests

**Workflow for code changes:**
1. Read `sessy_strategy.py` and `files/apps.yaml` for context
2. Read existing tests in `tests/`
3. Make the change
4. Write/update tests
5. Update `README.md` if behaviour or config changed
6. Run tests to verify

**This is the default — no special agent routing needed.**

---

## When to Use Agents vs. Default

| Task | Approach |
|------|----------|
| Single function/logic change | Default (inline) |
| New strategy priority rule | Default — follow workflow above |
| Tracing config across files | `Explore` agent |
| Refactoring helpers | `Explore` first, then default |
| Architecture question | `Explore` agent |

---

## Mandatory Rules for All Agents

### Code Changes:
1. ✅ Follow [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md)
2. ✅ Update `README.md` when behaviour or config changes
3. ✅ Write/update tests for any changed functionality
4. ✅ Run existing tests to verify no regressions

### Testing (Non-Negotiable):
1. ✅ Every new function gets at least one test
2. ✅ Every bug fix gets a regression test
3. ✅ Tests verify observable behaviour, not implementation details
4. ✅ Tests live in `tests/`
5. ✅ Run `pytest tests/ -v` before completing

---

**Last updated:** 2026-06-19
**Related:** [CONTRIBUTING.md](CONTRIBUTING.md), [CODING_PRINCIPLES.md](CODING_PRINCIPLES.md), [README.md](README.md)
