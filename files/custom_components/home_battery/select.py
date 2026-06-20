"""The Home Battery mode selector — the single master control.

The AppDaemon app reads this entity every cycle and either optimises, passes a
manual setpoint through, or stands down. Point apps.yaml at it:
``mode_select: select.home_battery_mode``.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_MODE, MODE_OPTIONS
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([HomeBatteryModeSelect(entry)])


class HomeBatteryModeSelect(SelectEntity, RestoreEntity):
    """Master mode selector, persisted across restarts."""

    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_icon = "mdi:home-battery"
    _attr_options = MODE_OPTIONS

    def __init__(self, entry: ConfigEntry):
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_device_info = device_info(entry)
        self._attr_current_option = DEFAULT_MODE

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in MODE_OPTIONS:
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
