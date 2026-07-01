"""Button platform: one-shot hot-water reload triggers."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_HOT_WATER_CIRCUITS, DEFAULT_HOT_WATER_CIRCUITS, HOT_WATER_RELOAD_VALUE
from .coordinator import GuntamaticConfigEntry, GuntamaticDataUpdateCoordinator
from .entity import GuntamaticEntity

# Serialize writes to the device (it processes one command at a time).
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuntamaticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up hot-water reload buttons (one per configured circuit)."""
    coordinator = entry.runtime_data
    circuits = int(entry.options.get(CONF_HOT_WATER_CIRCUITS, DEFAULT_HOT_WATER_CIRCUITS))

    entities: list[GuntamaticButton] = []
    for circuit in range(circuits):
        entities.append(
            GuntamaticButton(
                coordinator,
                key=f"hot_water_reload_{circuit}",
                translation_key="hot_water_reload",
                syn=f"BK{circuit}06",
                placeholders={"circuit": str(circuit)},
            )
        )
        entities.append(
            GuntamaticButton(
                coordinator,
                key=f"additional_hot_water_reload_{circuit}",
                translation_key="additional_hot_water_reload",
                syn=f"ZK{circuit}06",
                placeholders={"circuit": str(circuit)},
            )
        )
    async_add_entities(entities)


class GuntamaticButton(GuntamaticEntity, ButtonEntity):
    """A button that triggers a one-shot reload command."""

    def __init__(
        self,
        coordinator: GuntamaticDataUpdateCoordinator,
        *,
        key: str,
        translation_key: str,
        syn: str,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self._syn = syn
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        if placeholders is not None:
            self._attr_translation_placeholders = placeholders

    async def async_press(self) -> None:
        """Send the reload command."""
        await self.coordinator.async_set_parameter(self._syn, HOT_WATER_RELOAD_VALUE)
