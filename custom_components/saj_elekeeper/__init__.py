"""SAJ Elekeeper integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_PLANT_NAME, CONF_PLANT_UID, PLATFORMS
from .coordinator import ElekeeperDataUpdateCoordinator


@dataclass
class ElekeeperRuntimeData:
    """Runtime objects owned by one Elekeeper config entry."""

    coordinator: ElekeeperDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SAJ Elekeeper from a config entry."""
    old_default_titles = {
        entry.data.get(CONF_PLANT_NAME),
        entry.data.get(CONF_PLANT_UID),
    }
    if entry.title in old_default_titles:
        plant_name = entry.data.get(CONF_PLANT_NAME, entry.data[CONF_PLANT_UID])
        hass.config_entries.async_update_entry(entry, title=f"SAJ Elekeeper ({plant_name})")

    coordinator = ElekeeperDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ElekeeperRuntimeData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate existing entries and hide unlabeled raw API entities by default."""
    if entry.version < 2:
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if "_api_" in entity.unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SAJ Elekeeper config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.async_close()
    return unloaded
