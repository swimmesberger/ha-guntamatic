"""Diagnostics support for the Guntamatic (read/write) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import GuntamaticConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GuntamaticConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "channels": [
            {
                "id": channel.description.id,
                "name": channel.description.name,
                "type": channel.description.type,
                "unit": channel.description.unit,
                "value": channel.value,
            }
            for channel in coordinator.data.values()
        ],
    }
