"""Constants for the SAJ Elekeeper integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saj_elekeeper"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_PLANT_UID: Final = "plant_uid"
CONF_PLANT_NAME: Final = "plant_name"
CONF_REGION: Final = "region"
CONF_SCAN_INTERVAL_MINUTES: Final = "scan_interval_minutes"

REGION_EUROPE: Final = "europe"
REGION_CHINA: Final = "china"
REGION_OTHER: Final = "other"
DEFAULT_REGION: Final = REGION_EUROPE

REGION_BASE_URLS: Final[dict[str, str]] = {
    REGION_EUROPE: "https://eop.saj-electric.com",
    REGION_CHINA: "https://op.saj-electric.cn",
    REGION_OTHER: "https://iop.saj-electric.com",
}
REGION_OPTIONS: Final[dict[str, str]] = {
    REGION_EUROPE: "Europe (eop.saj-electric.com)",
    REGION_CHINA: "China (op.saj-electric.cn)",
    REGION_OTHER: "Other countries / regions (iop.saj-electric.com)",
}

DEFAULT_SCAN_INTERVAL_MINUTES: Final = 5
MIN_SCAN_INTERVAL_MINUTES: Final = 1
MAX_SCAN_INTERVAL_MINUTES: Final = 1440
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)
