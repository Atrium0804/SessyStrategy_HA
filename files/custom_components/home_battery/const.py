"""Constants for the Home Battery integration."""

DOMAIN = "home_battery"

# Device the integration groups every entity under.
DEVICE_NAME = "Home Battery"
MANUFACTURER = "SessyStrategy_HA"
MODEL = "Logical home battery"

# ── Config-entry keys: the underlying Sessy/AppDaemon entities we mirror ──────
# These map the integration onto your own Sessy entity IDs. Defaults match the
# standard SessyStrategy_HA entity suffixes — override per install.
CONF_SOC_SOURCE = "soc_source"
CONF_BATTERY_POWER_SOURCE = "battery_power_source"
CONF_GRID_POWER_SOURCE = "grid_power_source"
CONF_SYSTEM_STATE_SOURCE = "system_state_source"
CONF_SESSY_STRATEGY_SOURCE = "sessy_strategy_source"
CONF_STATUS_SOURCE = "status_source"
# The actual setpoint numbers Sessy is targeting (not the measured power above).
# The Actual setpoint sensor reports whichever one the active strategy drives.
CONF_GRID_SETPOINT_SOURCE = "grid_setpoint_source"
CONF_BATTERY_SETPOINT_SOURCE = "battery_setpoint_source"

DEFAULTS = {
    CONF_SOC_SOURCE: "sensor.sessy_battery_alt9_state_of_charge",
    CONF_BATTERY_POWER_SOURCE: "sensor.sessy_battery_alt9_power",
    CONF_GRID_POWER_SOURCE: "sensor.sessy_pwkn_p1_power",
    CONF_SYSTEM_STATE_SOURCE: "sensor.sessy_battery_alt9_system_state",
    CONF_SESSY_STRATEGY_SOURCE: "select.sessy_battery_alt9_power_strategy",
    CONF_STATUS_SOURCE: "sensor.sessy_strategy_status",
    CONF_GRID_SETPOINT_SOURCE: "number.sessy_pwkn_grid_target",
    CONF_BATTERY_SETPOINT_SOURCE: "number.sessy_battery_alt9_power_setpoint",
}

# ── Mode selector ────────────────────────────────────────────────────────────
# Labels must match what sessy_strategy.py normalises (lowercase, spaces → "_"):
#   optimized | grid_setpoint | battery_setpoint | sessy_dynamic | eco | idle
MODE_OPTIONS = [
    "Optimized",
    "Grid setpoint",
    "Battery setpoint",
    "Sessy dynamic",
    "Eco",
    "Idle",
]
DEFAULT_MODE = "Optimized"

PLATFORMS = ["sensor", "select", "number"]
