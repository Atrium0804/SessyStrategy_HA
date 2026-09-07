"""Per-rule enable switches for the Home Battery optimizer.

Each switch toggles one priority rule in the AppDaemon strategy. When a rule is
off the optimizer skips it and falls through to the next priority. Point
apps.yaml at these, e.g. ``rule_price_spike_entity: switch.home_battery_rule_price_spike``.
The grid-connection guard and the default fall-through are always active and are
deliberately not switchable.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import device_info


@dataclass(frozen=True)
class _Spec:
    key: str
    name: str
    icon: str


# One switch per optimizer priority rule. All default to on.
_SWITCHES: tuple[_Spec, ...] = (
    _Spec("rule_price_spike", "Rule: price-spike discharge", "mdi:transmission-tower-export"),
    _Spec("rule_cheap_charge", "Rule: cheap/negative charge", "mdi:transmission-tower-import"),
    _Spec("rule_afternoon_charge", "Rule: afternoon charge", "mdi:battery-charging-high"),
    _Spec("rule_evening_peak", "Rule: evening peak excess", "mdi:weather-sunset-down"),
    _Spec("rule_morning_selloff", "Rule: morning sell-off", "mdi:weather-sunset-up"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(HomeBatteryRuleSwitch(entry, spec) for spec in _SWITCHES)


class HomeBatteryRuleSwitch(SwitchEntity, RestoreEntity):
    """A persisted on/off switch enabling one optimizer rule."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, spec: _Spec):
        self._spec = spec
        # Pin the entity_id to the stable key so the friendly name can change
        # freely without altering the ID that apps.yaml and dashboards target.
        self.entity_id = f"switch.home_battery_{spec.key}"
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_device_info = device_info(entry)
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._attr_is_on = last.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
