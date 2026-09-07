---
title: Configure Seasonal Mode
doc_type: how-to
problem: "I want winter/summer behavior for my battery strategy"
solution: "Set up seasonal mode in apps.yaml or use live entity overrides"
audience: users
tags:
  - configuration
  - seasonal
  - winter
  - summer
created: 2026-08-01
last_updated: 2026-08-01
---

# How to Configure Seasonal Mode

**Problem:** You want your SessyStrategy to adapt its charging behavior based on the season — using winter timing for early evening peaks and summer timing for later peaks.

**Solution:** Configure seasonal mode either statically in `apps.yaml` or dynamically via a Home Assistant input_select entity that you can control from your dashboard.

---

## Related Documentation

- [Seasonal Operation Explained](../explanation/seasonal-operation.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [Live Tuning Entities](../reference/live-tuning-entities.md)

---

## Understanding Seasonal Mode

### What Seasonal Mode Does

SessyStrategy automatically adjusts its timing windows based on the season:

| Season | Afternoon Window | Behavior |
|--------|-----------------|----------|
| **Summer** | Default: 15:00-17:00 | Later charging window for summer evening peaks |
| **Winter** | Default: 14:00-18:00 | Earlier, wider charging window for winter evening peaks |

The strategy uses the hour of the day's minimum energy price to automatically infer the season:
- **Summer**: Minimum price occurs during daytime hours (default: 08:00-18:00)
- **Winter**: Minimum price occurs during nighttime hours (outside daytime range)

### When to Use Each Mode

| Mode | Use Case | Best For |
|------|----------|----------|
| `auto` | Automatic season detection | Most users — lets the strategy adapt automatically |
| `summer` | Force summer behavior | Users with consistent summer patterns |
| `winter` | Force winter behavior | Users with consistent winter patterns |

---

## Solution Steps

### Step 1: Configure the Season Mode

Season is configured statically in `apps.yaml` via the `season_mode` key.

Best for: consistent, predictable seasonal behavior.

**What to do:** Set the `season_mode` parameter in your `apps.yaml`.

**How to do it:**

1. Open your `apps.yaml` file in your AppDaemon configuration directory
2. Navigate to the `sessy_strategy` section
3. Set the `season_mode` parameter to one of: `auto`, `summer`, or `winter`

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  # Seasonal mode configuration
  season_mode: auto  # Options: auto, summer, winter
  season_day_start: 8    # Daytime start hour (default: 8)
  season_day_end: 18     # Daytime end hour (default: 18)
  season_auto_fallback: winter  # Fallback when auto detection fails
```

**Expected result:** The strategy will use the specified mode for all decisions.

### Step 2: Configure Winter-Specific Overrides (Optional)

If you need different behavior in winter vs. summer, you can set winter-specific overrides:

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  # Base values (used in summer and when not overridden)
  soc_floor: 20
  afternoon_start: 15
  afternoon_end: 17
  afternoon_window_h: 2.0

  # Winter-specific overrides
  soc_floor_winter: 0           # Override soc_floor to 0% in winter
  afternoon_start_winter: 14     # Start afternoon charge at 14:00 in winter
  afternoon_end_winter: 18       # End afternoon charge at 18:00 in winter
  afternoon_window_h_winter: 4.0 # Spread charge over 4 hours in winter
```

**When these apply:** Only when `season_mode` is set to `winter` (explicitly or via auto inference).

**Fallback behavior:** If a winter override is not set (or is `None`), the base value is used.

### Step 3: Configure Daylight Hours for Auto Detection

The `auto` mode uses these settings to determine if the minimum price hour is during "daylight":

```yaml
sessy_strategy:
  module: sessy_strategy
  class: SessyStrategy
  season_mode: auto
  season_day_start: 8    # Start of "daytime" for auto detection
  season_day_end: 18     # End of "daytime" for auto detection
  season_auto_fallback: winter  # Use this if auto detection fails
```

**How auto detection works:**
1. Strategy finds the hour with the lowest energy price for today
2. If that hour is between `season_day_start` and `season_day_end`, it's **summer**
3. Otherwise, it's **winter**
4. If detection fails (no price data), uses `season_auto_fallback`

---

## Verification

To confirm your seasonal mode is configured correctly:

1. **Check the status sensor:**
   - Look at `sensor.sessy_strategy_status` in Home Assistant
   - Check the `active_season` attribute — it should show: `auto`, `summer`, or `winter`
   - Check the `season_mode_source` attribute — shows where the mode came from

2. **Review the logs:**
   ```
   # In AppDaemon logs, look for:
   Season mode active: summer
   # or
   Season mode active: winter
   ```

3. **Test the behavior:**
   - In **summer mode**: Afternoon charging should occur around 15:00-17:00
   - In **winter mode**: Afternoon charging should start earlier (default 14:00)
   - Check that winter-specific overrides are applied when in winter mode

---

## Common Issues

### Issue 1: Season Mode Not Changing

**Symptom:** Status sensor always shows the same season regardless of configuration.

**Cause:**
- `season_mode` has a typo or an unexpected value in `apps.yaml`
- AppDaemon hasn't been restarted after configuration changes

**Fix:**
1. Verify `season_mode` is one of `auto`, `summer`, or `winter` in `apps.yaml`
2. Restart AppDaemon: `appdaemon restart`
3. Check the `active_season` attribute on the status sensor to confirm the resolved mode

### Issue 2: Auto Detection Always Returns Winter

**Symptom:** Strategy always detects winter season even when prices are low during the day.

**Cause:**
- Your energy price sensor doesn't provide `energy_prices` attribute
- The `season_day_start` and `season_day_end` range doesn't match your actual daylight hours
- No price data is available for today

**Fix:**
1. Verify your price sensor has the `energy_prices` attribute with 24 hourly prices
2. Adjust `season_day_start` and `season_day_end` to match your actual daylight:
   ```yaml
   season_day_start: 7   # Earlier for your location
   season_day_end: 19    # Later for your location
   ```
3. Set a different `season_auto_fallback` if winter isn't appropriate for your location

### Issue 3: Winter Overrides Not Applied

**Symptom:** Strategy uses base values even when in winter mode.

**Cause:**
- Winter override values are not set in `apps.yaml`
- The override values are set but are `None`
- There's a typo in the override parameter names

**Fix:**
1. Ensure winter overrides are properly set:
   ```yaml
   # Correct - numeric values
   soc_floor_winter: 0
   afternoon_start_winter: 14

   # Incorrect - these will be treated as None
   soc_floor_winter:
   afternoon_start_winter:
   ```
2. Verify the strategy is actually in winter mode by checking the status sensor

---

## Alternative Approaches

### Static Season Mode

**Pros:**
- Simple, reliable configuration
- No additional entities to create
- Predictable behavior

**Cons:**
- Manual changes require editing `apps.yaml` and restarting AppDaemon

**Steps:**
1. Set `season_mode` to your desired season (`auto`, `summer`, or `winter`)
2. Optionally set winter overrides if needed
3. Restart AppDaemon

---

## Best Practices

- [x] **Do:** Start with `season_mode: auto` to let the strategy adapt automatically
- [x] **Do:** Set winter overrides only if you need different winter behavior
- [x] **Do:** Monitor the `active_season` attribute in your status sensor
- ❌ **Don't:** Set winter overrides to the same values as base values (redundant)

---

## See Also

- [Seasonal Operation Explained](../explanation/seasonal-operation.md)
- [Configuration Reference — apps.yaml](../reference/configuration/apps-yaml.md)
- [How to Add Live Tuning Helpers](../how-to/add-live-tuning-helpers.md)
- [Debug Strategy Decisions](../how-to/debug-strategy-decisions.md)

---

## Quick Checklist

- [ ] Set `season_mode` (`auto`, `summer`, or `winter`) in apps.yaml
- [ ] Configured winter overrides if needed
- [ ] Verified status sensor shows correct `active_season`
- [ ] Confirmed winter overrides are applied when in winter mode

---

*Last updated: 2026-08-01*