# Coding Principles — SessyStrategy HA

**Status:** Mandatory for all code contributions
**Effective Date:** 2026-06-19

These principles guide all development on this AppDaemon Home Assistant application. They are enforced through code review and AI-assisted development (GitHub Copilot).

---

## Core Principles

### 1. Structure

**Use a consistent, predictable project layout**
- New contributors should immediately understand where to find things
- Strategy logic lives in `files/sessy_strategy.py`; configuration lives in `files/apps.yaml`
- Helper modules (e.g. `sessy_helpers.yaml`) stay separate from core strategy logic

**Keep the strategy class lean**
- `initialize()` reads config and schedules the callback; nothing more
- `update_strategy()` is the single decision entry point
- Extract reusable calculations into named helper methods

**Identify shared logic before duplicating**
- Before copying a formula to a second place, extract a helper method
- If you find yourself making the same fix in multiple places, refactor

> ⚠️ **Anti-pattern:** Duplication that requires the same fix in multiple places is a code smell, not a pattern to preserve.

---

### 2. Architecture

**Prefer flat, explicit code over abstractions or deep hierarchies**
```python
# Good: Flat and explicit
def _calc_charge_setpoint(self, soc, soc_target, hours_remaining):
    gap_wh = (soc_target - soc) / 100 * self.capacity_wh
    raw = gap_wh / max(hours_remaining, 0.083)  # avoid div/0
    return min(raw, self.c_rate_cap * self.capacity_wh, self.max_power_w)

# Bad: Unnecessary abstraction
class SetpointCalculatorFactory:
    def get_calculator(self, mode):
        return self._registry[mode]()
```

**Avoid clever patterns and unnecessary indirection**
- Code should be readable without deep Python expertise
- Prefer explicit conditionals over complex dispatch tables
- If you need a comment to explain *how* the code works, simplify it

**Keep AppDaemon coupling explicit**
- All HA entity reads/writes go through clearly named helper calls
- Avoid storing HA state in instance variables between cycles; re-read each run

---

### 3. Functions and Methods

**Keep the main decision function linear and readable**
```python
# Good: Linear priority flow — each priority is a clear if/elif branch
def update_strategy(self, kwargs):
    soc, price = self._read_sensors()
    if price > self.price_discharge:
        return self._apply_discharge(soc)
    if price < self.price_charge:
        return self._apply_cheap_charge(soc)
    if self._in_prepeak_window() and self._prepeak_worthwhile(soc, price):
        return self._apply_prepeak_charge(soc)
    self._apply_grid_zero()

# Bad: Deeply nested conditionals mixing concerns
def update_strategy(self, kwargs):
    if not self._is_disabled():
        season = self._get_season()
        if season == "summer":
            if price > threshold:
                if soc > floor:
                    ...
```

**Use small helper methods; avoid deeply nested logic**
- Extract each priority rule into its own `_apply_*` method
- Maximum nesting depth: 3 levels
- Helper methods that only read or compute (no side effects) are easy to test

**Pass state through method arguments, not instance variables**
- `soc` and `price` should be parameters, not stored on `self` between cycles
- `self.*` instance variables are reserved for configuration set in `initialize()`

---

### 4. Naming and Comments

**Use descriptive-but-simple names**
```python
# Good
def _calc_spread_setpoint(self, gap_pct, window_hours):
    ...

# Bad: Too terse
def _csp(self, g, w):
    ...

# Bad: Too verbose
def _calculate_proportional_spread_setpoint_from_gap_and_window(self, gap_pct, window_hours):
    ...
```

**Comment only to note invariants, assumptions, or non-obvious behaviour**
```python
# Good: Explains WHY
def _calc_spread_setpoint(self, gap_pct, window_hours):
    # Inverter copper losses scale with I²; partial power is far more efficient
    gap_wh = gap_pct / 100 * self.capacity_wh
    return gap_wh / max(window_hours, 0.083)

# Bad: Explains WHAT (code already shows this)
def _calc_spread_setpoint(self, gap_pct, window_hours):
    # Divide gap_wh by window_hours
    gap_wh = gap_pct / 100 * self.capacity_wh
    return gap_wh / window_hours
```

---

### 5. Logging and Errors

**Use AppDaemon's `self.log()` at key decision boundaries**
```python
def update_strategy(self, kwargs):
    soc, price = self._read_sensors()
    if soc is None or price is None:
        self.log("Skipping cycle: sensor unavailable", level="WARNING")
        return
    self.log(f"Cycle: soc={soc:.1f}% price={price:.4f}")
    ...
    self.log(f"Decision: discharge at {setpoint}W (price spike {price:.4f})")
```

**Log the decision and its reason every cycle** so the AppDaemon log is a readable audit trail.

**Make errors explicit and informative**
```python
# Good: Specific, actionable
if soc is None:
    self.log(
        f"SOC sensor '{self.soc_sensor}' returned None — check entity ID in apps.yaml",
        level="WARNING"
    )
    return

# Bad: Silent or vague
if soc is None:
    return
```

---

### 6. Configuration

**All tunables live in `apps.yaml`; none are hardcoded in the Python file**
```yaml
# Good: all thresholds in apps.yaml
price_discharge: 0.39
price_charge: -0.10
min_arbitrage_margin: 0.05
```

**Read tunables in `initialize()` with safe defaults**
```python
# Good: safe default, overridable from apps.yaml
self.price_discharge = float(self.args.get("price_discharge", 0.39))

# Bad: magic number buried in strategy logic
if price > 0.39:
    ...
```

**Optional live-tuning entities**: if `*_entity` keys are set in `apps.yaml`, their value overrides the static default each cycle. Document this pattern in README.md for any new tunable.

---

### 7. Platform Use

**Use AppDaemon idioms directly**
- Read entity states with `self.get_state(entity_id, attribute=...)` — never cache HA state on `self`
- Schedule recurring work with `self.run_every()` in `initialize()`
- Call HA services with `self.call_service()`
- Log with `self.log()`, not `print()` or the stdlib `logging` module

**Follow PEP 8 for Python style**
- Private helpers use the `_` prefix: `_calc_setpoint`, `_in_prepeak_window`
- Use `float()` / `int()` casts when reading sensor states; sensors return strings

**`apps.yaml` stays human-readable**
- Group related keys with comments (see existing file)
- Boolean flags as `true`/`false`, numbers unquoted

---

### 8. Modifications

**Read surrounding code before making changes**
- Match existing style, naming conventions, and structure
- New priority rules go *before* the default `grid_setpoint = 0W` branch
- If you deviate from an existing pattern, add a comment explaining why

**Keep `sessy_strategy.py` self-contained**
- The file should be readable top-to-bottom: `initialize` → `update_strategy` → helpers
- No circular imports; no external helper files beyond AppDaemon itself

---

### 9. Quality

**Extract pure helper functions so they can be tested without AppDaemon**
```python
# Good: Pure function, easily unit-tested
def _calc_spread_setpoint(gap_pct, capacity_wh, window_hours, c_rate_cap, max_power_w):
    gap_wh = gap_pct / 100 * capacity_wh
    raw = gap_wh / max(window_hours, 0.083)
    return min(raw, c_rate_cap * capacity_wh, max_power_w)

# Bad: Logic buried in method that requires a live HA connection to test
def update_strategy(self, kwargs):
    gap_wh = (self.soc_target - float(self.get_state(self.soc_sensor))) / 100 * self.capacity_wh
    ...
```

**Keep tests simple and focused on observable behaviour**
```python
# Good
def test_discharge_setpoint_tapers_as_soc_approaches_floor():
    high = _calc_spread_setpoint(40, 5000, 2.0, 0.4, 2200)  # 40% above floor
    low  = _calc_spread_setpoint(10, 5000, 2.0, 0.4, 2200)  # 10% above floor
    assert high > low

# Bad: Tests implementation details
def test_update_strategy_calls_call_service():
    with mock.patch.object(app, "call_service") as m:
        app.update_strategy({})
        assert m.called
```

---

## Enforcement

These principles are enforced through:

1. **Code Review** — PRs must follow these principles
2. **GitHub Copilot** — Configured to follow these principles
3. **Tests** — `pytest tests/ -v` must pass before merging

---

## Related Documentation

- [README.md](README.md) — Full strategy explanation and configuration reference
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution workflow and checklist
- [files/apps.yaml](files/apps.yaml) — All tunables and entity IDs
- [files/sessy_strategy.py](files/sessy_strategy.py) — Strategy implementation

---

**Questions or Exceptions?**
If a situation requires deviating from these principles, add a comment in the code explaining why. Never deviate silently.
Ask the user when making key decisions