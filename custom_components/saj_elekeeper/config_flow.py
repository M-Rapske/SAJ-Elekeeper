"""Config and options flows for SAJ Elekeeper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import voluptuous as vol
from elekeeper import SajApiError, SajAuthError
from elekeeper.models import PlantListEntry

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlowWithReload
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import async_create_client
from .const import (
    CONF_PLANT_NAME,
    CONF_PLANT_UID,
    CONF_REGION,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    REGION_EUROPE,
    REGION_OPTIONS,
)


async def _async_validate_account(
    hass: HomeAssistant,
    user_input: Mapping[str, Any],
) -> list[PlantListEntry]:
    """Verify credentials and return the visible Elekeeper plants."""
    client = await async_create_client(
        hass, region=str(user_input.get(CONF_REGION, DEFAULT_REGION))
    )
    try:
        await client.authenticate(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        return await client.list_plants(page_size=100)
    finally:
        await client.aclose()


class SajElekeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the SAJ Elekeeper configuration flow."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SajElekeeperOptionsFlow:
        """Create the Elekeeper options flow."""
        return SajElekeeperOptionsFlow()

    def __init__(self) -> None:
        """Set up transient flow state."""
        self._account_data: dict[str, str] = {}
        self._plants: dict[str, PlantListEntry] = {}
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Collect the portal region and account credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                plants = await _async_validate_account(self.hass, user_input)
            except (SajAuthError, SajApiError):
                errors["base"] = "invalid_auth"
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            else:
                if not plants:
                    errors["base"] = "no_plants"
                else:
                    self._account_data = user_input
                    self._plants = {plant.uid: plant for plant in plants}
                    if len(plants) == 1:
                        return await self._async_create_entry(plants[0])
                    return await self.async_step_plant()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=DEFAULT_REGION): vol.In(
                        REGION_OPTIONS
                    ),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_plant(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Select a plant when the account has several."""
        if user_input is not None:
            return await self._async_create_entry(self._plants[user_input[CONF_PLANT_UID]])

        choices = {plant.uid: plant.name or plant.uid for plant in self._plants.values()}
        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema({vol.Required(CONF_PLANT_UID): vol.In(choices)}),
        )

    async def _async_create_entry(self, plant: PlantListEntry) -> dict[str, Any]:
        """Create an entry for the selected plant."""
        region = self._account_data[CONF_REGION]
        unique_id = plant.uid if region == REGION_EUROPE else f"{region}:{plant.uid}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"SAJ Elekeeper ({plant.name or plant.uid})",
            data={
                **self._account_data,
                CONF_PLANT_UID: plant.uid,
                CONF_PLANT_NAME: plant.name or plant.uid,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Start a password-only reauthentication flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Update a changed Elekeeper password."""
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            new_data = {
                **self._reauth_entry.data,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await _async_validate_account(self.hass, new_data)
            except (SajAuthError, SajApiError):
                errors["base"] = "invalid_auth"
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class SajElekeeperOptionsFlow(OptionsFlowWithReload):
    """Configure the Elekeeper polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Manage the update interval through Home Assistant's UI."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL_MINUTES, default=interval): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_MINUTES,
                            max=MAX_SCAN_INTERVAL_MINUTES,
                            step=1,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
