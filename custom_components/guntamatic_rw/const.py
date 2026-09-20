"""Constants for the Guntamatic (read/write) integration."""

from __future__ import annotations

from dataclasses import dataclass
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

# Names of the DAQ string channels that report the CURRENT program state, so the
# control selects can reflect the real device state instead of being optimistic.
# Note: some firmwares misspell "Programm" as "Progamm" for the heating circuits.
CONTROL_PROGRAM_STATE_NAMES: Final = ("Programm",)
HEATING_PROGRAM_STATE_NAMES: Final = ("Progamm HK{n}", "Programm HK{n}")

# Reverse maps: device status string (upper-cased) -> select option key.
CONTROL_PROGRAM_STATE_MAP: Final[dict[str, str]] = {
    "AUS": "off",
    "NORMAL": "normal",
    "WARMWASSER": "hot_water",
    "HEIZEN": "heat",
    "ABSENKEN": "setback",
    "HANDBETRIEB": "manual",
}
HEATING_PROGRAM_STATE_MAP: Final[dict[str, str]] = {
    "AUS": "off",
    "NORMAL": "normal",
    "HEIZEN": "heat",
    "ABSENKEN": "setback",
}

# DAQ units that always denote a numeric channel (used for keyless type inference).
NUMERIC_UNITS: Final = ("°C", "%", "h", "d", "m3")

# Channel names in the keyless daqdesc that are placeholders and must be skipped.
RESERVED_CHANNEL_NAMES: Final = ("reserved", "")

# DAQ channels that are only meaningful while the burner is alight. The lambda
# probe must be hot to produce a valid signal: once the fire is out and the
# induced-draft fan stops, the derived reading drifts upwards and clamps at a
# plausible-looking value instead of dropping out, which silently poisons any
# long-term statistic built on the channel.
COMBUSTION_ONLY_CHANNEL_NAMES: Final = ("CO2 Gehalt",)

# Channel reporting burner output in %, used to gate the channels above.
BURNER_OUTPUT_CHANNEL_NAME: Final = "Leistung"


@dataclass(frozen=True)
class ParSensorDef:
    """A curated par.cgi parameter exposed as a diagnostic sensor."""

    par_id: str
    translation_key: str
    icon: str | None = None


# Diagnostic sensors sourced from par.cgi (keyless). Focused on the hybrid/heat-pump
# configuration, which is otherwise invisible in the DAQ data.
PAR_SENSORS: Final[tuple[ParSensorDef, ...]] = (
    ParSensorDef("PR004", "operating_mode", "mdi:heat-pump"),
    ParSensorDef("WP015", "hybrid_mode", "mdi:scale-balance"),
    ParSensorDef("WP001", "dhw_source_summer", "mdi:water-boiler"),
    ParSensorDef("AE042", "cop_limit", "mdi:speedometer"),
    ParSensorDef("WP006", "pellet_price", "mdi:currency-eur"),
    ParSensorDef("WP007", "power_price_day", "mdi:transmission-tower"),
    ParSensorDef("WP008", "power_price_night", "mdi:transmission-tower-off"),
    ParSensorDef("FK005a", "buffer_setpoint_hp", "mdi:thermometer-water"),
)
