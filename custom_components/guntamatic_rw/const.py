"""Constants for the Guntamatic (read/write) integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "guntamatic_rw"
MANUFACTURER: Final = "Guntamatic"
DEFAULT_NAME: Final = "Guntamatic"

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

# Polling
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600

# Config / options keys
CONF_HEATING_CIRCUITS: Final = "heating_circuits"
CONF_HOT_WATER_CIRCUITS: Final = "hot_water_circuits"
CONF_BOILER_SYNONYM: Final = "boiler_synonym"

DEFAULT_HEATING_CIRCUITS: Final = 1
DEFAULT_HOT_WATER_CIRCUITS: Final = 0
MAX_HEATING_CIRCUITS: Final = 9  # HK0..HK8
MAX_HOT_WATER_CIRCUITS: Final = 3  # circuits 0..2

# Boiler-release (Kesselfreigabe) synonym differs by product family.
# Source: docs/WEB-MODBUS-Schnittstelle_DE, section "Einstellen der Kesselfreigabe".
BOILER_SYNONYM_PK: Final = "PK002"  # Powerchip / Powercorn / Biocom / Pro
BOILER_SYNONYM_K: Final = "K0010"  # Therm / Biostar
BOILER_SYNONYMS: Final = [BOILER_SYNONYM_PK, BOILER_SYNONYM_K]
DEFAULT_BOILER_SYNONYM: Final = BOILER_SYNONYM_PK

# Control-program synonym is model independent.
CONTROL_PROGRAM_SYNONYM: Final = "PR001"

# Value to trigger a (one-shot) hot-water reload.
HOT_WATER_RELOAD_VALUE: Final = 1

# Option-key -> device value maps. Keys double as select `translation_key` states.
# Source: docs/WEB-MODBUS-Schnittstelle_DE, section "Externe Befehle".
BOILER_MODE_OPTIONS: Final[dict[str, int]] = {
    "auto": 0,
    "off": 1,
    "on": 2,  # "Dauer" / continuous
}

CONTROL_PROGRAM_OPTIONS: Final[dict[str, int]] = {
    "off": 0,
    "normal": 1,
    "hot_water": 2,
    "heat": 3,
    "setback": 4,
    "manual": 8,  # Handbetrieb (only PC/BC/PH/TH/BS/PRO)
}

HEATING_PROGRAM_OPTIONS: Final[dict[str, int]] = {
    "off": 0,
    "normal": 1,
    "heat": 2,
    "setback": 3,
}
