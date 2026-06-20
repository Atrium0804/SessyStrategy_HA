"""The Home Battery integration.

Tier 1: a thin device + entity shell over the existing SessyStrategy_HA
AppDaemon app. It creates one "Home Battery" device that owns:

  * the mode select + setpoint/SOC numbers the user drives (and the app reads),
  * mirror sensors of the underlying Sessy entities + the app's status sensor.

The AppDaemon app keeps making every decision. Point apps.yaml at the entities
this integration creates (e.g. ``mode_select: select.home_battery_mode``).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Battery from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = dict(entry.data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (source entity IDs) change."""
    await hass.config_entries.async_reload(entry.entry_id)
