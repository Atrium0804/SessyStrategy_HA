"""Shared device info so every entity lands on one Home Battery device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_info import DeviceInfo

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER, MODEL


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """One device, identified by the config entry, shared by all entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEVICE_NAME,
        manufacturer=MANUFACTURER,
        model=MODEL,
    )
