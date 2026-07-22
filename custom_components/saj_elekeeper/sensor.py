"""Sensor entities for SAJ Elekeeper plants and non-plug components."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElekeeperDataUpdateCoordinator
from .models import ElekeeperDevice, ElekeeperPlantData, ScalarValue

PLANT_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="pv_power_w",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="load_power_w",
        translation_key="load_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="grid_power_w",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="battery_power_w",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="self_use_power_w",
        translation_key="self_use_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="battery_soc_percent",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="battery_soh_percent",
        translation_key="battery_soh",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="battery_voltage_v",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="battery_current_a",
        translation_key="battery_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key="battery_temperature_c",
        translation_key="battery_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(key="mode", translation_key="operating_mode"),
    SensorEntityDescription(key="grid_direction", translation_key="grid_direction"),
    SensorEntityDescription(key="battery_direction", translation_key="battery_direction"),
)

_DAY_ENERGY_FIELDS: tuple[tuple[str, str], ...] = (
    ("today_pv_energy_kwh", "today_pv_energy"),
    ("today_load_energy_kwh", "today_load_energy"),
    ("today_grid_import_kwh", "today_grid_import"),
    ("today_grid_export_kwh", "today_grid_export"),
    ("today_battery_charge_kwh", "today_battery_charge"),
    ("today_battery_discharge_kwh", "today_battery_discharge"),
)
_TOTAL_ENERGY_FIELDS: tuple[tuple[str, str], ...] = (
    ("total_pv_energy_kwh", "total_pv_energy"),
    ("total_load_energy_kwh", "total_load_energy"),
    ("total_grid_import_kwh", "total_grid_import"),
    ("total_grid_export_kwh", "total_grid_export"),
    ("total_battery_charge_kwh", "total_battery_charge"),
    ("total_battery_discharge_kwh", "total_battery_discharge"),
)
PLANT_SENSOR_DESCRIPTIONS += tuple(
    SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    )
    for key, translation_key in _DAY_ENERGY_FIELDS
)
PLANT_SENSOR_DESCRIPTIONS += tuple(
    SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    )
    for key, translation_key in _TOTAL_ENERGY_FIELDS
)

DEVICE_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="status", translation_key="device_status"),
    SensorEntityDescription(key="mode", translation_key="device_mode"),
    SensorEntityDescription(
        key="power_w",
        translation_key="device_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="charge_energy_kwh",
        translation_key="device_charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="today_energy_kwh",
        translation_key="device_today_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="total_energy_kwh",
        translation_key="device_total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="battery_soc_percent",
        translation_key="device_battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="temperature_c",
        translation_key="device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="today_alarm_count",
        translation_key="device_alarm_count",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

_PV_KEYS = frozenset(
    {"pv_power_w", "today_pv_energy_kwh", "total_pv_energy_kwh"}
)
_GRID_KEYS = frozenset(
    {
        "grid_power_w",
        "grid_direction",
        "today_grid_import_kwh",
        "today_grid_export_kwh",
        "total_grid_import_kwh",
        "total_grid_export_kwh",
    }
)
_BATTERY_KEYS = frozenset(
    {
        "battery_power_w",
        "battery_soc_percent",
        "battery_soh_percent",
        "battery_voltage_v",
        "battery_current_a",
        "battery_temperature_c",
        "battery_direction",
        "today_battery_charge_kwh",
        "today_battery_discharge_kwh",
        "total_battery_charge_kwh",
        "total_battery_discharge_kwh",
    }
)
_LOAD_KEYS = frozenset({"load_power_w", "today_load_energy_kwh", "total_load_energy_kwh"})


def _plant_device_group(sensor_key: str) -> str:
    """Return the virtual device group owning a plant-level sensor."""
    if sensor_key in _PV_KEYS:
        return "pv"
    if sensor_key in _GRID_KEYS:
        return "grid"
    if sensor_key in _BATTERY_KEYS:
        return "battery"
    if sensor_key in _LOAD_KEYS:
        return "load"
    return "plant"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all non-plug entities reported for one Elekeeper plant."""
    coordinator: ElekeeperDataUpdateCoordinator = entry.runtime_data.coordinator
    plant = coordinator.data
    entities: list[SensorEntity] = [
        ElekeeperPlantSensor(coordinator, description)
        for description in PLANT_SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        ElekeeperPlantApiSensor(coordinator, key) for key in plant.additional_values
    )
    for device in plant.devices:
        entities.extend(
            ElekeeperDeviceSensor(coordinator, device.serial, description)
            for description in DEVICE_SENSOR_DESCRIPTIONS
        )
        entities.extend(
            ElekeeperDeviceApiSensor(coordinator, device.serial, key)
            for key in device.additional_values
        )
    async_add_entities(entities)


def _humanize_api_key(key: str) -> str:
    """Turn an API field name into a readable entity name."""
    key = key.replace("__", " ")
    key = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
    return key.replace("_", " ").strip().title()


class _ElekeeperEntity(CoordinatorEntity[ElekeeperDataUpdateCoordinator], SensorEntity):
    """Shared device-registration behavior for Elekeeper sensor entities."""

    _attr_has_entity_name = True

    def _plant_device_info(self) -> DeviceInfo:
        plant = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, plant.uid)},
            name=f"SAJ Elekeeper ({plant.name or plant.uid})",
            manufacturer="SAJ",
            model="Elekeeper plant",
        )

    def _plant_group_device_info(self, group: str) -> DeviceInfo:
        """Register PV, grid, battery, and load as their own HA devices."""
        if group == "plant":
            return self._plant_device_info()

        plant = self.coordinator.data
        labels = {
            "pv": ("SAJ PV System", "PV monitoring"),
            "grid": ("SAJ Grid Connection", "Grid monitoring"),
            "battery": ("SAJ Battery System", "Battery monitoring"),
            "load": ("SAJ Home Consumption", "Load monitoring"),
        }
        name, model = labels[group]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{plant.uid}_{group}")},
            name=name,
            manufacturer="SAJ",
            model=model,
            via_device=(DOMAIN, plant.uid),
        )


class ElekeeperPlantSensor(_ElekeeperEntity):
    """Represent one known live plant metric."""

    def __init__(
        self,
        coordinator: ElekeeperDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"plant_{coordinator.data.uid}_{description.key}"

    @property
    def native_value(self) -> str | float | int | None:
        return getattr(self.coordinator.data, self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        return self._plant_group_device_info(
            _plant_device_group(self.entity_description.key)
        )


class ElekeeperPlantApiSensor(_ElekeeperEntity):
    """Represent a scalar API value not covered by the known plant schema."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ElekeeperDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = _humanize_api_key(key)
        self._attr_unique_id = f"plant_{coordinator.data.uid}_api_{key}"

    @property
    def native_value(self) -> ScalarValue | None:
        return self.coordinator.data.additional_values.get(self._key)

    @property
    def device_info(self) -> DeviceInfo:
        return self._plant_device_info()


class _ElekeeperDeviceEntity(_ElekeeperEntity):
    """Shared behavior for one non-plug Elekeeper component."""

    def __init__(self, coordinator: ElekeeperDataUpdateCoordinator, serial: str) -> None:
        super().__init__(coordinator)
        self._serial = serial

    def _device(self) -> ElekeeperDevice | None:
        return next(
            (device for device in self.coordinator.data.devices if device.serial == self._serial),
            None,
        )

    @property
    def available(self) -> bool:
        return super().available and self._device() is not None

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device()
        model = device.model if device and device.model else "Elekeeper component"
        if device and device.is_wallbox:
            name = device.name or f"SAJ Wallbox {self._serial[-6:]}"
            model = device.model or "EV Charger"
        else:
            name = (
                device.name
                if device and device.name
                else f"SAJ {model} {self._serial[-6:]}"
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            name=name,
            manufacturer="SAJ",
            model=model,
            serial_number=self._serial,
            via_device=(DOMAIN, self.coordinator.data.uid),
        )


class ElekeeperDeviceSensor(_ElekeeperDeviceEntity):
    """Represent one standard metric of a non-plug component."""

    def __init__(
        self,
        coordinator: ElekeeperDataUpdateCoordinator,
        serial: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"device_{serial}_{description.key}"

    @property
    def native_value(self) -> str | float | int | None:
        device = self._device()
        return getattr(device, self.entity_description.key) if device else None


class ElekeeperDeviceApiSensor(_ElekeeperDeviceEntity):
    """Represent a scalar device API value outside the standard schema."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: ElekeeperDataUpdateCoordinator,
        serial: str,
        key: str,
    ) -> None:
        super().__init__(coordinator, serial)
        self._key = key
        self._attr_name = _humanize_api_key(key)
        self._attr_unique_id = f"device_{serial}_api_{key}"

    @property
    def native_value(self) -> ScalarValue | None:
        device = self._device()
        return device.additional_values.get(self._key) if device else None
