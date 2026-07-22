"""Local models for Elekeeper plant and non-plug device data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from elekeeper.models import BatteryInfo, EnergyFlow, PlantInfo, PlantStatistics

ScalarValue = str | int | float | bool

_SENSITIVE_KEY_PARTS = frozenset(
    {"token", "password", "secret", "authorization", "credential"}
)
_IDENTITY_KEYS = frozenset(
    {
        "plantUid",
        "deviceSn",
        "batterySn",
        "deviceName",
        "deviceModel",
        "batteryModel",
        "deviceType",
        "deviceTypeName",
        "smartDeviceType",
        "smartDeviceTypeName",
    }
)
_KNOWN_PLANT_KEYS = frozenset(
    {
        "dataTime",
        "updateDate",
        "userModeName",
        "powerNow",
        "todayPvEnergy",
        "todayLoadEnergy",
        "todayBuyEnergy",
        "todaySellEnergy",
        "todayBatChgEnergy",
        "todayBatDischgEnergy",
        "totalPvEnergy",
        "totalLoadEnergy",
        "totalBuyEnergy",
        "totalSellEnergy",
        "totalBatChgEnergy",
        "totalBatDischgEnergy",
        "totalPvPower",
        "solarPower",
        "totalLoadPowerwatt",
        "sysGridPowerwatt",
        "gridDirection",
        "batteryDirection",
        "selfUsePower",
        "batEnergyPercent",
        "batSohPercent",
        "batPower",
        "batVoltage",
        "batCurrent",
        "batTemperature",
        "todayBatDisEnergy",
        "batteryWorkTime",
    }
)
_KNOWN_DEVICE_KEYS = _KNOWN_PLANT_KEYS | frozenset(
    {
        "deviceStatus",
        "deviceStatusName",
        "runningState",
        "onlineStatusName",
        "chargingStatus",
        "chargingStatusName",
        "chargepileStatusName",
        "invTemp",
        "temperature",
        "todayAlarmNum",
        "alarmCount",
        "todayEnergy",
        "todayChargeEnergy",
        "chargeEnergyToday",
        "totalEnergy",
        "totalChargeEnergy",
        "chargeEnergy",
        "chargePower",
        "chargingPower",
        "outputPower",
        "devicePower",
    }
)


def _as_float(value: Any) -> float | None:
    """Convert an API value to float when possible."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    """Convert a non-empty API value to the string required by device registry."""
    if value is None or value == "":
        return None
    return str(value)


def _first_value(data: Mapping[str, Any], *keys: str) -> Any:
    """Return the first present non-empty API value."""
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def _scalar_values(
    raw_sources: Mapping[str, Mapping[str, Any]], known_keys: frozenset[str]
) -> dict[str, ScalarValue]:
    """Expose non-standard scalar API fields without credentials or duplicates."""
    values: dict[str, ScalarValue] = {}
    for source, data in raw_sources.items():
        for key, value in data.items():
            normalized_key = key.casefold()
            if (
                key in known_keys
                or key in _IDENTITY_KEYS
                or any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)
                or not isinstance(value, (str, int, float, bool))
            ):
                continue
            if isinstance(value, str) and len(value) > 255:
                continue
            values[f"{source}__{key}"] = value
    return values


def is_smart_plug(data: Mapping[str, Any]) -> bool:
    """Identify Smart Plugs so this integration never creates their entities."""
    smart_device_type = data.get("smartDeviceType")
    if smart_device_type is not None:
        # V2 uses a stable numeric device type: 1 is a Smart Plug, while the
        # AC011K Wallbox is type 6.
        return str(smart_device_type) == "1"

    description = " ".join(
        str(data.get(key, ""))
        for key in (
            "smartDeviceTypeName",
            "deviceTypeName",
            "deviceModel",
            "batteryModel",
            "deviceName",
        )
    ).casefold().strip()
    return (
        "smart plug" in description
        or "smart socket" in description
        or description.startswith("sp16")
    )


def is_wallbox(data: Mapping[str, Any]) -> bool:
    """Identify Elekeeper's V2 EV Charger device category."""
    if str(data.get("smartDeviceType")) == "6":
        return True
    description = " ".join(
        str(data.get(key, ""))
        for key in ("smartDeviceTypeName", "chargerType", "deviceModel")
    ).casefold()
    return "ev charger" in description or "wallbox" in description


@dataclass(frozen=True)
class ElekeeperDevice:
    """A non-plug component reported by Elekeeper."""

    serial: str
    name: str | None = None
    model: str | None = None
    kind: str | None = None
    status: str | None = None
    mode: str | None = None
    power_w: float | None = None
    charge_energy_kwh: float | None = None
    today_energy_kwh: float | None = None
    total_energy_kwh: float | None = None
    battery_soc_percent: float | None = None
    temperature_c: float | None = None
    today_alarm_count: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_raw(cls, data: Mapping[str, Any]) -> ElekeeperDevice | None:
        """Create a device model from a V1 device or battery-list row."""
        if is_smart_plug(data):
            return None
        serial = _first_value(data, "deviceSn", "batterySn", "sn")
        if serial is None:
            return None

        alarm_value = _first_value(data, "todayAlarmNum", "alarmCount")
        try:
            alarm_count = int(alarm_value) if alarm_value is not None else None
        except (TypeError, ValueError):
            alarm_count = None

        return cls(
            serial=str(serial),
            name=_as_str(_first_value(data, "deviceName", "batteryName")),
            model=_as_str(
                _first_value(
                    data,
                    "deviceModel",
                    "batteryModel",
                    "deviceTypeName",
                    "smartDeviceTypeName",
                    "chargerType",
                )
            ),
            kind=_as_str(
                _first_value(
                    data,
                    "deviceTypeName",
                    "smartDeviceTypeName",
                    "deviceType",
                    "batteryType",
                )
            ),
            status=_as_str(
                _first_value(
                    data,
                    "deviceStatusName",
                    "chargingStatusName",
                    "chargepileStatusName",
                    "onlineStatusName",
                    "deviceStatus",
                    "runningState",
                    "chargingStatus",
                )
            ),
            mode=_as_str(_first_value(data, "userModeName", "workModeName")),
            power_w=_as_float(
                _first_value(
                    data,
                    "solarPower",
                    "powerNow",
                    "power",
                    "chargePower",
                    "chargingPower",
                    "outputPower",
                    "devicePower",
                )
            ),
            charge_energy_kwh=_as_float(data.get("chargeEnergy")),
            today_energy_kwh=_as_float(
                _first_value(
                    data,
                    "todayEnergy",
                    "todayPvEnergy",
                    "todayChargeEnergy",
                    "chargeEnergyToday",
                )
            ),
            total_energy_kwh=_as_float(
                _first_value(data, "totalEnergy", "totalPvEnergy", "totalChargeEnergy")
            ),
            battery_soc_percent=_as_float(data.get("batEnergyPercent")),
            temperature_c=_as_float(_first_value(data, "invTemp", "temperature")),
            today_alarm_count=alarm_count,
            raw=dict(data),
        )

    @property
    def additional_values(self) -> dict[str, ScalarValue]:
        """Return scalar device values not represented by a standard sensor."""
        return _scalar_values({"api": self.raw}, _KNOWN_DEVICE_KEYS)

    @property
    def is_wallbox(self) -> bool:
        """Return whether this component is an Elekeeper EV Charger."""
        return is_wallbox(self.raw)


@dataclass(frozen=True)
class ElekeeperPlantData:
    """Current plant power, energy, battery, weather, and component data."""

    uid: str
    name: str | None = None
    device_sn: str | None = None
    updated_at: str | None = None
    mode: str | None = None
    pv_power_w: float | None = None
    load_power_w: float | None = None
    grid_power_w: float | None = None
    grid_direction: str | None = None
    battery_power_w: float | None = None
    battery_direction: str | None = None
    battery_soc_percent: float | None = None
    battery_soh_percent: float | None = None
    battery_voltage_v: float | None = None
    battery_current_a: float | None = None
    battery_temperature_c: float | None = None
    self_use_power_w: float | None = None
    today_pv_energy_kwh: float | None = None
    today_load_energy_kwh: float | None = None
    today_grid_import_kwh: float | None = None
    today_grid_export_kwh: float | None = None
    today_battery_charge_kwh: float | None = None
    today_battery_discharge_kwh: float | None = None
    total_pv_energy_kwh: float | None = None
    total_load_energy_kwh: float | None = None
    total_grid_import_kwh: float | None = None
    total_grid_export_kwh: float | None = None
    total_battery_charge_kwh: float | None = None
    total_battery_discharge_kwh: float | None = None
    devices: tuple[ElekeeperDevice, ...] = ()
    raw: dict[str, Mapping[str, Any]] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(
        cls,
        plant_uid: str,
        plant_info: PlantInfo,
        statistics: PlantStatistics,
        flow: EnergyFlow,
        battery: BatteryInfo | None,
        weather: Mapping[str, Any] | None,
        devices: tuple[ElekeeperDevice, ...],
    ) -> ElekeeperPlantData:
        """Build the stable live-data model from client endpoint results."""
        return cls(
            uid=plant_uid,
            name=plant_info.name,
            device_sn=plant_info.primary_device_sn,
            updated_at=statistics.updated_at,
            mode=(battery.mode if battery else None) or statistics.mode,
            # ``powerNow`` can be a stale zero on the statistics endpoint;
            # the live energy-flow endpoint is the more current source.
            pv_power_w=flow.pv_power_w or statistics.pv_power_w,
            load_power_w=flow.load_power_w,
            grid_power_w=flow.grid_power_w,
            grid_direction=flow.grid_direction,
            battery_power_w=battery.power_w if battery else None,
            battery_direction=(battery.direction if battery else None)
            or flow.battery_direction,
            battery_soc_percent=battery.soc_percent if battery else None,
            battery_soh_percent=battery.soh_percent if battery else None,
            battery_voltage_v=battery.voltage_v if battery else None,
            battery_current_a=battery.current_a if battery else None,
            battery_temperature_c=battery.temperature if battery else None,
            self_use_power_w=flow.self_use_power_w,
            today_pv_energy_kwh=statistics.today_pv_energy_kwh,
            today_load_energy_kwh=statistics.today_load_energy_kwh,
            today_grid_import_kwh=statistics.today_grid_import_kwh,
            today_grid_export_kwh=statistics.today_grid_export_kwh,
            today_battery_charge_kwh=statistics.today_battery_charge_kwh,
            today_battery_discharge_kwh=statistics.today_battery_discharge_kwh,
            total_pv_energy_kwh=statistics.total_pv_energy_kwh,
            total_load_energy_kwh=statistics.total_load_energy_kwh,
            total_grid_import_kwh=statistics.total_grid_import_kwh,
            total_grid_export_kwh=statistics.total_grid_export_kwh,
            total_battery_charge_kwh=statistics.total_battery_charge_kwh,
            total_battery_discharge_kwh=statistics.total_battery_discharge_kwh,
            devices=devices,
            raw={
                "statistics": statistics.raw,
                "flow": flow.raw,
                "battery": battery.raw if battery else {},
                "weather": dict(weather or {}),
            },
        )

    @property
    def additional_values(self) -> dict[str, ScalarValue]:
        """Return scalar plant data not covered by the standard entities."""
        return _scalar_values(self.raw, _KNOWN_PLANT_KEYS)
