"""Mirror sensors for the Home Battery device.

These follow the underlying Sessy entities (and the AppDaemon status sensor) and
re-publish them under the Home Battery device.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_BATTERY_POWER_SOURCE,
    CONF_GRID_POWER_SOURCE,
    CONF_SESSY_STRATEGY_SOURCE,
    CONF_SOC_SOURCE,
    CONF_STATUS_SOURCE,
    CONF_SYSTEM_STATE_SOURCE,
    DEFAULTS,
)
from .entity import device_info

_UNKNOWN = ("unknown", "unavailable", None)


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the mirror sensors."""
    cfg = {**DEFAULTS, **entry.data}
    async_add_entities(
        [
            HomeBatteryNumericSensor(
                entry,
                key="soc",
                name="SOC",
                source=cfg[CONF_SOC_SOURCE],
                device_class=SensorDeviceClass.BATTERY,
                unit=PERCENTAGE,
                icon="mdi:battery",
            ),
            HomeBatteryNumericSensor(
                entry,
                key="charge_power",
                name="Charge power",
                source=cfg[CONF_BATTERY_POWER_SOURCE],
                device_class=SensorDeviceClass.POWER,
                unit=UnitOfPower.WATT,
                icon="mdi:battery-charging",
            ),
            HomeBatteryNumericSensor(
                entry,
                key="grid_power",
                name="Grid power",
                source=cfg[CONF_GRID_POWER_SOURCE],
                device_class=SensorDeviceClass.POWER,
                unit=UnitOfPower.WATT,
                icon="mdi:transmission-tower",
            ),
            HomeBatteryTextSensor(
                entry,
                key="system_state",
                name="System state",
                sources=[cfg[CONF_SYSTEM_STATE_SOURCE]],
                icon="mdi:state-machine",
                value_fn=lambda hass: _state(hass, cfg[CONF_SYSTEM_STATE_SOURCE]),
            ),
            HomeBatteryActiveStrategySensor(
                entry,
                mode_entity="select.home_battery_mode",
                sessy_strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                status_entity=cfg[CONF_STATUS_SOURCE],
            ),
            HomeBatteryTextSensor(
                entry,
                key="active_substrategy",
                name="Active sub-strategy",
                sources=[cfg[CONF_STATUS_SOURCE]],
                icon="mdi:source-branch",
                value_fn=lambda hass: _attr(
                    hass, cfg[CONF_STATUS_SOURCE], "active_branch"
                ),
            ),
        ]
    )


def _state(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNKNOWN:
        return None
    return state.state


def _attr(hass: HomeAssistant, entity_id: str, attr: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    value = state.attributes.get(attr)
    return None if value in _UNKNOWN else value


class _BaseSensor(SensorEntity):
    """Common wiring: device, source tracking, initial refresh."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str, name: str, sources: list[str]):
        self._sources = sources
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sources, self._handle_source_event
            )
        )
        self._refresh()

    @callback
    def _handle_source_event(self, _event: Event) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class HomeBatteryNumericSensor(_BaseSensor):
    """Mirror a single numeric source entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        key: str,
        name: str,
        source: str,
        device_class: SensorDeviceClass,
        unit: str,
        icon: str,
    ):
        super().__init__(entry, key, name, [source])
        self._source = source
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    def _refresh(self) -> None:
        state = self.hass.states.get(self._source)
        value = _as_float(state.state) if state else None
        self._attr_native_value = value
        self._attr_available = value is not None


class HomeBatteryActiveStrategySensor(_BaseSensor):
    """The mode the user selected, with what Sessy/the app actually did as attrs.

    State mirrors the mode select; attributes surface the underlying Sessy
    power_strategy and the app's last decision branch so you can confirm the
    request was honoured.
    """

    _attr_icon = "mdi:strategy"

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        mode_entity: str,
        sessy_strategy_entity: str,
        status_entity: str,
    ):
        super().__init__(
            entry,
            "active_strategy",
            "Active strategy",
            [mode_entity, sessy_strategy_entity, status_entity],
        )
        self._mode_entity = mode_entity
        self._sessy_strategy_entity = sessy_strategy_entity
        self._status_entity = status_entity

    def _refresh(self) -> None:
        self._attr_native_value = _state(self.hass, self._mode_entity)
        self._attr_available = self._attr_native_value is not None
        self._attr_extra_state_attributes = {
            "sessy_strategy": _state(self.hass, self._sessy_strategy_entity),
            "active_branch": _attr(self.hass, self._status_entity, "active_branch"),
        }


class HomeBatteryTextSensor(_BaseSensor):
    """A text sensor whose value is computed from one or more sources."""

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        key: str,
        name: str,
        sources: list[str],
        icon: str,
        value_fn: Callable[[HomeAssistant], str | None],
    ):
        super().__init__(entry, key, name, sources)
        self._attr_icon = icon
        self._value_fn = value_fn

    def _refresh(self) -> None:
        value = self._value_fn(self.hass)
        self._attr_native_value = value
        self._attr_available = value is not None
