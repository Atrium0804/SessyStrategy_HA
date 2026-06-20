"""Config + options flow for Home Battery.

A single screen maps the integration onto your Sessy entity IDs. Defaults match
files/home_battery.yaml, so on a standard install you can just press Submit.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_BATTERY_POWER_SOURCE,
    CONF_GRID_POWER_SOURCE,
    CONF_SESSY_STRATEGY_SOURCE,
    CONF_SOC_SOURCE,
    CONF_STATUS_SOURCE,
    CONF_SYSTEM_STATE_SOURCE,
    DEFAULTS,
    DEVICE_NAME,
    DOMAIN,
)

_SENSOR = EntitySelector(EntitySelectorConfig(domain="sensor"))
_SELECT = EntitySelector(EntitySelectorConfig(domain="select"))


def _schema(values: dict[str, Any]) -> vol.Schema:
    """Build the form schema, pre-filled from values (config defaults)."""
    return vol.Schema(
        {
            vol.Required(CONF_SOC_SOURCE, default=values[CONF_SOC_SOURCE]): _SENSOR,
            vol.Required(
                CONF_BATTERY_POWER_SOURCE, default=values[CONF_BATTERY_POWER_SOURCE]
            ): _SENSOR,
            vol.Required(
                CONF_GRID_POWER_SOURCE, default=values[CONF_GRID_POWER_SOURCE]
            ): _SENSOR,
            vol.Required(
                CONF_SYSTEM_STATE_SOURCE, default=values[CONF_SYSTEM_STATE_SOURCE]
            ): _SENSOR,
            vol.Required(
                CONF_SESSY_STRATEGY_SOURCE, default=values[CONF_SESSY_STRATEGY_SOURCE]
            ): _SELECT,
            vol.Required(
                CONF_STATUS_SOURCE, default=values[CONF_STATUS_SOURCE]
            ): _SENSOR,
        }
    )


class HomeBatteryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        # Single logical device — only allow one entry.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=DEVICE_NAME, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_schema(dict(DEFAULTS))
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> "HomeBatteryOptionsFlow":
        return HomeBatteryOptionsFlow()


class HomeBatteryOptionsFlow(OptionsFlow):
    """Let the user remap source entities after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            # Persist into entry.data so platforms read one place.
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            return self.async_create_entry(title="", data={})

        current = {**DEFAULTS, **self.config_entry.data}
        return self.async_show_form(
            step_id="init", data_schema=_schema(current)
        )
