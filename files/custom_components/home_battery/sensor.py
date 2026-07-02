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
    CONF_BATTERY_SETPOINT_SOURCE,
    CONF_GRID_POWER_SOURCE,
    CONF_GRID_SETPOINT_SOURCE,
    CONF_SESSY_STRATEGY_SOURCE,
    CONF_SOC_SOURCE,
    CONF_STATUS_SOURCE,
    CONF_SYSTEM_STATE_SOURCE,
    DEFAULTS,
)
from .entity import device_info

_UNKNOWN = ("unknown", "unavailable", None)

# Maps the AppDaemon active_branch key to a user-friendly label.
# Unmapped keys (manual modes, stand-down modes) pass through as-is.
_BRANCH_NAMES: dict[str, str] = {
    "discharge":           "Price spike — discharging",
    "cheap_charge":        "Cheap price — charging",
    "cheap_charge_full":   "Cheap price — battery full",
    "prepeak_charge":      "Pre-peak — charging",
    "prepeak_full":        "Pre-peak — battery full",
    "prepeak_skip":        "Pre-peak — price too high",
    "evening_peak_excess": "Evening peak — discharging",
    "default":             "Idle — self consumption mode",
    "manual_grid":         "Manual — grid setpoint",
    "manual_battery":      "Manual — battery setpoint",
    "idle":                "Idle — Sessy standby",
    "sessy_dynamic":       "Sessy's own dynamic schedule",
    "eco":                 "Eco mode",
}


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
                key="battery_power",
                name="Battery power",
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
                name="Sessy state",
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
                key="sessy_strategy",
                name="Sessy strategy",
                sources=[cfg[CONF_SESSY_STRATEGY_SOURCE]],
                icon="mdi:transmission-tower-import",
                value_fn=lambda hass: _state(hass, cfg[CONF_SESSY_STRATEGY_SOURCE]),
            ),
            HomeBatteryActualSetpointSensor(
                entry,
                sessy_strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                grid_setpoint_entity=cfg[CONF_GRID_SETPOINT_SOURCE],
                battery_setpoint_entity=cfg[CONF_BATTERY_SETPOINT_SOURCE],
            ),
            # Requested vs actual setpoint, split per branch so each charts as a
            # clean line that only has data while its strategy drives Sessy.
            HomeBatteryGatedSetpointSensor(
                entry,
                key="requested_grid_setpoint",
                name="Requested grid setpoint",
                icon="mdi:transmission-tower-export",
                strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                when_strategy="nom",
                value_entity="number.home_battery_setpoint",
            ),
            HomeBatteryGatedSetpointSensor(
                entry,
                key="requested_battery_setpoint",
                name="Requested battery setpoint",
                icon="mdi:battery-charging",
                strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                when_strategy="api",
                value_entity="number.home_battery_setpoint",
            ),
            HomeBatteryGatedSetpointSensor(
                entry,
                key="actual_grid_setpoint",
                name="Actual grid setpoint",
                icon="mdi:transmission-tower",
                strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                when_strategy="nom",
                value_entity=cfg[CONF_GRID_SETPOINT_SOURCE],
            ),
            HomeBatteryGatedSetpointSensor(
                entry,
                key="actual_battery_setpoint",
                name="Actual battery setpoint",
                icon="mdi:flash",
                strategy_entity=cfg[CONF_SESSY_STRATEGY_SOURCE],
                when_strategy="api",
                value_entity=cfg[CONF_BATTERY_SETPOINT_SOURCE],
            ),
            HomeBatteryTextSensor(
                entry,
                key="active_substrategy",
                name="Active rule",
                sources=[cfg[CONF_STATUS_SOURCE]],
                icon="mdi:source-branch",
                value_fn=lambda hass: _BRANCH_NAMES.get(
                    raw := _attr(hass, cfg[CONF_STATUS_SOURCE], "active_branch"),
                    raw,
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
        # Pin entity_id to the stable key so friendly-name renames don't break references.
        self.entity_id = f"sensor.home_battery_{key}"
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
            "Power strategy",
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


class HomeBatteryActualSetpointSensor(_BaseSensor):
    """The setpoint Sessy is actually targeting right now.

    The requested setpoint is ``number.home_battery_setpoint``; this sensor
    reports what Sessy actually applied. The active ``power_strategy`` decides
    which physical setpoint is live: ``nom`` drives the grid target, ``api``
    drives the battery power. The ``operates_on`` attribute records which one
    (``grid`` / ``battery``), or ``None`` when Sessy runs its own strategy and
    neither setpoint is being driven.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:flash"

    # Sessy power_strategy option → which setpoint it drives.
    _OPERATES_ON = {"nom": "grid", "api": "battery"}

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        sessy_strategy_entity: str,
        grid_setpoint_entity: str,
        battery_setpoint_entity: str,
    ):
        super().__init__(
            entry,
            "actual_setpoint",
            "Actual setpoint",
            [sessy_strategy_entity, grid_setpoint_entity, battery_setpoint_entity],
        )
        self._sessy_strategy_entity = sessy_strategy_entity
        self._grid_setpoint_entity = grid_setpoint_entity
        self._battery_setpoint_entity = battery_setpoint_entity

    def _refresh(self) -> None:
        strategy = _state(self.hass, self._sessy_strategy_entity)
        operates_on = self._OPERATES_ON.get(strategy)
        source = {
            "grid": self._grid_setpoint_entity,
            "battery": self._battery_setpoint_entity,
        }.get(operates_on)

        value = None
        if source is not None:
            state = self.hass.states.get(source)
            value = _as_float(state.state) if state else None

        self._attr_native_value = value
        self._attr_available = value is not None
        self._attr_extra_state_attributes = {"operates_on": operates_on}


class HomeBatteryGatedSetpointSensor(_BaseSensor):
    """A power setpoint that only reports while its strategy is the live one.

    ``nom`` drives the grid target, ``api`` the battery power. Gating each
    requested/actual setpoint to its strategy keeps chart lines clean: a line
    only carries data while its branch is active and goes unavailable otherwise,
    so the pairs never overlap or drag a stale value across a strategy switch.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        key: str,
        name: str,
        icon: str,
        strategy_entity: str,
        when_strategy: str,
        value_entity: str,
    ):
        super().__init__(entry, key, name, [strategy_entity, value_entity])
        self._attr_icon = icon
        self._strategy_entity = strategy_entity
        self._when_strategy = when_strategy
        self._value_entity = value_entity

    def _refresh(self) -> None:
        value = None
        if _state(self.hass, self._strategy_entity) == self._when_strategy:
            state = self.hass.states.get(self._value_entity)
            value = _as_float(state.state) if state else None
        self._attr_native_value = value
        self._attr_available = value is not None


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
