"""User-tunable numbers for the Home Battery device.

The AppDaemon app reads these each cycle (manual setpoints in the matching modes,
SOC targets always). Point apps.yaml at them, e.g.
``soc_target_entity: number.home_battery_soc_target``.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import device_info


@dataclass(frozen=True)
class _Spec:
    key: str
    name: str
    icon: str
    minimum: float
    maximum: float
    step: float
    unit: str
    initial: float
    mode: NumberMode


# Controls exposed on the Home Battery device.
_NUMBERS: tuple[_Spec, ...] = (
    _Spec(
        "grid_setpoint", "Grid setpoint", "mdi:transmission-tower",
        -10000, 10000, 50, UnitOfPower.WATT, 0, NumberMode.BOX,
    ),
    _Spec(
        "battery_setpoint", "Battery setpoint", "mdi:battery-charging",
        -2200, 2200, 50, UnitOfPower.WATT, 0, NumberMode.BOX,
    ),
    _Spec(
        "soc_target", "SOC target", "mdi:battery-charging-90",
        0, 100, 1, PERCENTAGE, 90, NumberMode.SLIDER,
    ),
    _Spec(
        "soc_floor", "SOC floor", "mdi:battery-20",
        0, 100, 1, PERCENTAGE, 20, NumberMode.SLIDER,
    ),
    _Spec(
        "soc_ceiling", "SOC ceiling", "mdi:battery-charging-100",
        0, 100, 1, PERCENTAGE, 100, NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(HomeBatteryNumber(entry, spec) for spec in _NUMBERS)


class HomeBatteryNumber(NumberEntity, RestoreEntity):
    """A persisted, user-settable number on the Home Battery device."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, spec: _Spec):
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_min_value = spec.minimum
        self._attr_native_max_value = spec.maximum
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_mode = spec.mode
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_device_info = device_info(entry)
        self._attr_native_value = spec.initial

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            try:
                self._attr_native_value = float(last.state)
            except (TypeError, ValueError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
