"""Select platform: control writes via parset.cgi.

For the control program and per-circuit heating program the device exposes the
current value as a DAQ string channel ("Programm" / "Progamm HKx"), so those
selects reflect the REAL device state. The boiler-release select has no such
tri-state channel (only a boolean), so it stays optimistic: the shown option is
the last command issued from Home Assistant (restored across restarts).
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
    CONTROL_PROGRAM_STATE_MAP,
    CONTROL_PROGRAM_STATE_NAMES,
    CONTROL_PROGRAM_SYNONYM,
    DEFAULT_BOILER_SYNONYM,
    DEFAULT_HEATING_CIRCUITS,
    HEATING_PROGRAM_OPTIONS,
    HEATING_PROGRAM_STATE_MAP,
    HEATING_PROGRAM_STATE_NAMES,
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

    # Resolve the "current state" channel ids by (case-insensitive) name.
    by_name = {desc.name.strip().casefold(): desc.id for desc in coordinator.descriptions}

    def resolve(*names: str) -> int | None:
        for name in names:
            channel_id = by_name.get(name.strip().casefold())
            if channel_id is not None:
                return channel_id
        return None

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
            state_channel_id=resolve(*CONTROL_PROGRAM_STATE_NAMES),
            state_value_map=CONTROL_PROGRAM_STATE_MAP,
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
                state_channel_id=resolve(
                    *(name.format(n=circuit) for name in HEATING_PROGRAM_STATE_NAMES)
                ),
                state_value_map=HEATING_PROGRAM_STATE_MAP,
            )
        )

    async_add_entities(entities)


class GuntamaticSelect(GuntamaticEntity, RestoreEntity, SelectEntity):
    """A select that writes a parameter, reflecting real state when available."""

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
        state_channel_id: int | None = None,
        state_value_map: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._syn = syn
        self._options_map = dict(options_map)
        self._state_channel_id = state_channel_id
        self._state_value_map = dict(state_value_map) if state_value_map else {}
        self._attr_translation_key = translation_key
        self._attr_options = list(options_map)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        if placeholders is not None:
            self._attr_translation_placeholders = dict(placeholders)

    async def async_added_to_hass(self) -> None:
        """Restore the last selected option (used as optimistic fallback)."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._options_map:
                self._attr_current_option = last_state.state

    @property
    def current_option(self) -> str | None:
        """Return the current option, preferring real device state."""
        if self._state_channel_id is not None:
            channel = self.coordinator.data.get(self._state_channel_id)
            if channel is not None and channel.value is not None:
                mapped = self._state_value_map.get(str(channel.value).strip().upper())
                if mapped in self._options_map:
                    return mapped
        # Fall back to the last command issued (optimistic / restored).
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Write the chosen option to the device."""
        await self.coordinator.async_set_parameter(self._syn, self._options_map[option])
        self._attr_current_option = option
        self.async_write_ha_state()
