"""Data coordinator for SAJ Elekeeper."""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from datetime import timedelta
import logging
from typing import Any, Final, TypeVar

import httpx
from elekeeper import SajApiError, SajAuthError, SajClient
from elekeeper.models import BatteryInfo, EnergyFlow, PlantInfo, PlantStatistics

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_create_client, async_post_v2
from .const import (
    CONF_PLANT_UID,
    CONF_REGION,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .models import ElekeeperDevice, ElekeeperPlantData, is_smart_plug

_LOGGER = logging.getLogger(__name__)
_AUTH_STATUS_CODES: Final = {401, 403}
_LOGIN_REQUIRED_API_CODE: Final = 10002
_SMART_DEVICE_LIST_PATH: Final = "/api/v2/monitor/plantDevice/listSmartDeviceForWeb"
_T = TypeVar("_T")


def _device_discovery_rows(
    source: Mapping[str, Any] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return a redacted summary of discovered API rows for diagnostics."""
    rows = source.get("list") if isinstance(source, Mapping) else source
    if not isinstance(rows, list):
        return []

    summary: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        serial = row.get("deviceSn") or row.get("batterySn")
        summary.append(
            {
                "serial_suffix": str(serial)[-6:] if serial else None,
                "model": row.get("deviceModel") or row.get("smartDeviceTypeName"),
                "device_type": row.get("deviceType") or row.get("smartDeviceType"),
                "field_names": sorted(row),
            }
        )
    return summary


def _is_login_required_error(error: SajApiError) -> bool:
    """Return whether Elekeeper asks the client to authenticate again."""
    error_code = getattr(error, "code", getattr(error, "error_code", None))
    return error_code == _LOGIN_REQUIRED_API_CODE or (
        f"SAJ API error {_LOGIN_REQUIRED_API_CODE}:" in str(error)
    )


def _get_scan_interval(entry: ConfigEntry) -> timedelta:
    """Return the configured whole-minute polling interval."""
    try:
        minutes = int(entry.options.get(CONF_SCAN_INTERVAL_MINUTES))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL
    minutes = min(max(minutes, MIN_SCAN_INTERVAL_MINUTES), MAX_SCAN_INTERVAL_MINUTES)
    return timedelta(minutes=minutes)


class ElekeeperDataUpdateCoordinator(DataUpdateCoordinator[ElekeeperPlantData]):
    """Fetch non-plug live data for one Elekeeper plant."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator without contacting the cloud."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=_get_scan_interval(entry),
            always_update=False,
        )
        self.config_entry = entry
        self._client: SajClient | None = None
        self._org_code: str | None = None
        self.last_optional_errors: dict[str, str] = {}
        self.device_discovery: dict[str, list[dict[str, Any]]] = {}

    async def _async_setup(self) -> None:
        """Authenticate once before the initial data refresh."""
        self._client = await async_create_client(
            self.hass,
            region=self.config_entry.data.get(CONF_REGION, DEFAULT_REGION),
        )
        await self._async_authenticate()

    async def _async_authenticate(self) -> None:
        """Authenticate without ever logging credentials."""
        if self._client is None:
            self._client = await async_create_client(
                self.hass,
                region=self.config_entry.data.get(CONF_REGION, DEFAULT_REGION),
            )
        try:
            await self._client.authenticate(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
            self._org_code = None
        except (SajAuthError, SajApiError) as err:
            raise ConfigEntryAuthFailed("Elekeeper rejected the credentials") from err
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Unable to authenticate with Elekeeper: {err}") from err

    async def _async_update_data(self) -> ElekeeperPlantData:
        """Request data, retrying once after token expiry."""
        try:
            return await self._async_fetch_data()
        except SajAuthError as err:
            raise ConfigEntryAuthFailed("Elekeeper authentication expired") from err
        except SajApiError as err:
            if not _is_login_required_error(err):
                raise UpdateFailed(f"Error communicating with Elekeeper: {err}") from err
        except httpx.HTTPStatusError as err:
            if err.response.status_code not in _AUTH_STATUS_CODES:
                raise UpdateFailed(f"Error communicating with Elekeeper: {err}") from err
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Error communicating with Elekeeper: {err}") from err

        await self._async_authenticate()
        try:
            return await self._async_fetch_data()
        except SajAuthError as err:
            raise ConfigEntryAuthFailed("Elekeeper authentication expired") from err
        except (SajApiError, httpx.HTTPError) as err:
            raise UpdateFailed(f"Error communicating with Elekeeper: {err}") from err

    async def _async_fetch_data(self) -> ElekeeperPlantData:
        """Collect stable power, energy, battery, and non-plug device data."""
        if self._client is None:
            raise RuntimeError("Elekeeper client was not initialized")

        self.last_optional_errors = {}
        plant_uid = self.config_entry.data[CONF_PLANT_UID]
        login_info = await self._client.get_login_info()
        org_code = login_info.raw.get("orgCode")
        if isinstance(org_code, str):
            self._org_code = org_code
        plant_info = await self._client.get_plant_info(plant_uid)
        device_sn = plant_info.primary_device_sn
        statistics = await self._client.get_plant_statistics_data(
            plant_uid, device_sn=device_sn
        )
        flow = await self._client.get_device_energy_flow(plant_uid, device_sn=device_sn)

        battery = await self._optional_call(
            "battery",
            self._client.get_one_device_battery_info(device_sn)
            if device_sn
            else None,
        )
        weather = await self._optional_call(
            "weather", self._client.get_current_weather(plant_uid)
        )
        device_list = await self._optional_call(
            "device_list",
            self._client.get_device_list(
                plant_uid,
                page_size=100,
                search_office_id_arr=login_info.office_id,
            ),
        )
        battery_list = await self._optional_call(
            "battery_list",
            self._client.get_battery_list(
                plant_uid,
                page_size=100,
                search_office_id_arr=login_info.office_id,
            ),
        )
        smart_device_list = await self._optional_call(
            "smart_device_list", self._async_fetch_v2_smart_devices(plant_uid)
        )
        self.device_discovery = {
            "v1_devices": _device_discovery_rows(device_list),
            "v1_batteries": _device_discovery_rows(battery_list),
            "v2_smart_devices": _device_discovery_rows(
                smart_device_list if isinstance(smart_device_list, list) else []
            ),
        }
        _LOGGER.debug("Elekeeper device discovery: %s", self.device_discovery)
        devices = await self._async_build_devices(
            plant_uid,
            device_list,
            battery_list,
            smart_device_list if isinstance(smart_device_list, list) else [],
        )

        return ElekeeperPlantData.from_api(
            plant_uid,
            plant_info,
            statistics,
            flow,
            battery if isinstance(battery, BatteryInfo) else None,
            weather if isinstance(weather, Mapping) else None,
            devices,
        )

    async def _optional_call(
        self, name: str, request: Awaitable[_T] | None
    ) -> _T | None:
        """Run a nonessential endpoint without failing all primary entities."""
        if request is None:
            return None
        try:
            return await request
        except (SajApiError, httpx.HTTPError) as err:
            self.last_optional_errors[name] = str(err)
            _LOGGER.debug("Elekeeper optional endpoint %s failed: %s", name, err)
            return None

    async def _async_fetch_v2_smart_devices(
        self, plant_uid: str
    ) -> list[dict[str, Any]]:
        """Return V2 smart devices, such as the Elekeeper Wallbox, but not plugs."""
        if self._client is None:
            return []
        response = await async_post_v2(
            self._client,
            _SMART_DEVICE_LIST_PATH,
            {"plantUid": plant_uid},
            org_code=self._org_code,
        )
        devices = response.get("smartDeviceList")
        if not isinstance(devices, list):
            return []
        return [device for device in devices if isinstance(device, dict)]

    async def _async_build_devices(
        self,
        plant_uid: str,
        device_list: Mapping[str, Any] | None,
        battery_list: Mapping[str, Any] | None,
        smart_device_list: list[dict[str, Any]],
    ) -> tuple[ElekeeperDevice, ...]:
        """Merge V1 device details and battery rows, excluding every Smart Plug."""
        if self._client is None:
            return ()

        raw_devices: dict[str, dict[str, Any]] = {}
        for source in (device_list, battery_list):
            for row in (source or {}).get("list") or []:
                if not isinstance(row, Mapping) or is_smart_plug(row):
                    continue
                serial = row.get("deviceSn") or row.get("batterySn")
                if serial:
                    raw_devices.setdefault(str(serial), {}).update(row)

        for row in smart_device_list:
            if is_smart_plug(row):
                continue
            serial = row.get("deviceSn")
            if serial:
                raw_devices.setdefault(str(serial), {}).update(row)

        devices: list[ElekeeperDevice] = []
        for serial, raw in raw_devices.items():
            if raw.get("smartDeviceType") is None:
                detail = await self._optional_call(
                    f"device_{serial}", self._client.get_one_device_info(serial)
                )
                if detail is not None:
                    raw.update(detail.raw)
            # The V2 detail endpoint is Smart-Plug-specific and can return a
            # plug payload for a Wallbox serial. Its list row is therefore
            # intentionally used unchanged for all V2 smart devices.
            device = ElekeeperDevice.from_raw(raw)
            if device is not None:
                devices.append(device)

        return tuple(devices)

    async def async_close(self) -> None:
        """Close the underlying HTTP client when the config entry unloads."""
        if self._client is not None:
            await self._client.aclose()
