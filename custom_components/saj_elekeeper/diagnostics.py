"""Diagnostics for SAJ Elekeeper without sensitive data."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_PLANT_NAME, CONF_PLANT_UID, CONF_REGION, DEFAULT_REGION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return a compact runtime summary without credentials or raw API data."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data
    return {
        "entry": {
            "username_configured": bool(entry.data.get(CONF_USERNAME)),
            "region": entry.data.get(CONF_REGION, DEFAULT_REGION),
            "plant_uid": entry.data.get(CONF_PLANT_UID),
            "plant_name": entry.data.get(CONF_PLANT_NAME),
        },
        "plant": {
            "device_count": len(data.devices),
            "device_models": [device.model for device in data.devices],
            "optional_api_errors": coordinator.last_optional_errors,
            "api_device_discovery": coordinator.device_discovery,
        },
    }
