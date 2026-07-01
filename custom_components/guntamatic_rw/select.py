"""Select platform: control writes via parset.cgi.

Guntamatic's web interface does not expose the *current* value of the control
parameters as dedicated, model-independent DAQ channels, so these selects are
optimistic: the shown option reflects the last command issued from Home
Assistant (restored across restarts), not a value read back from the device.
"""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    BOILER_MODE_OPTIONS,
    CONF_BOILER_SYNONYM,
    CONF_HEATING_CIRCUITS,
    CONTROL_PROGRAM_OPTIONS,
    CONTROL_PROGRAM_SYNONYM,
    DEFAULT_BOILER_SYNONYM,
    DEFAULT_HEATING_CIRCUITS,
    HEATING_PROGRAM_OPTIONS,
)
from .coordinator import GuntamaticConfigEntry, GuntamaticDataUpdateCoordinator
from .entity import GuntamaticEntity

# Serialize writes to the device (it processes one command at a time).
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuntamaticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the control selects."""
    coordinator = entry.runtime_data
    options = entry.options

    boiler_syn = options.get(CONF_BOILER_SYNONYM, DEFAULT_BOILER_SYNONYM)
    heating_circuits = int(options.get(CONF_HEATING_CIRCUITS, DEFAULT_HEATING_CIRCUITS))

    entities: list[GuntamaticSelect] = [
        GuntamaticSelect(
            coordinator,
            key="boiler_mode",
            translation_key="boiler_mode",
            syn=boiler_syn,
            options_map=BOILER_MODE_OPTIONS,
        ),
        GuntamaticSelect(
            coordinator,
            key="control_program",
            translation_key="control_program",
            syn=CONTROL_PROGRAM_SYNONYM,
            options_map=CONTROL_PROGRAM_OPTIONS,
        ),
    ]

    for circuit in range(heating_circuits):
        entities.append(
            GuntamaticSelect(
                coordinator,
                key=f"heating_program_{circuit}",
                translation_key="heating_program",
                syn=f"HK{circuit}01",
                options_map=HEATING_PROGRAM_OPTIONS,
                placeholders={"circuit": str(circuit)},
            )
        )

    async_add_entities(entities)


class GuntamaticSelect(GuntamaticEntity, RestoreEntity, SelectEntity):
    """An optimistic select that writes a parameter to the device."""

    _attr_current_option: str | None = None

    def __init__(
        self,
        coordinator: GuntamaticDataUpdateCoordinator,
        *,
        key: str,
        translation_key: str,
        syn: str,
        options_map: Mapping[str, int],
        placeholders: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._syn = syn
        self._options_map = dict(options_map)
        self._attr_translation_key = translation_key
        self._attr_options = list(options_map)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        if placeholders is not None:
            self._attr_translation_placeholders = dict(placeholders)

    async def async_added_to_hass(self) -> None:
        """Restore the last selected option."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._options_map:
                self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Write the chosen option to the device."""
        await self.coordinator.async_set_parameter(self._syn, self._options_map[option])
        self._attr_current_option = option
        self.async_write_ha_state()
