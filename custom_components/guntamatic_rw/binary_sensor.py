"""Binary sensor platform: one entity per boolean DAQ channel."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GuntamaticConfigEntry, GuntamaticDataUpdateCoordinator
from .entity import GuntamaticEntity

# Read-only platform: allow unlimited parallel updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuntamaticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for boolean channels."""
    coordinator = entry.runtime_data
    entities = [
        GuntamaticBinarySensor(coordinator, channel_id)
        for channel_id, channel in coordinator.data.items()
        if channel.description.type == "bool"
    ]
    async_add_entities(entities)


class GuntamaticBinarySensor(GuntamaticEntity, BinarySensorEntity):
    """A binary sensor backed by one boolean DAQ channel."""

    def __init__(
        self, coordinator: GuntamaticDataUpdateCoordinator, channel_id: int
    ) -> None:
        """Initialize the binary sensor for a given channel id."""
        super().__init__(coordinator)
        self._channel_id = channel_id
        desc = coordinator.data[channel_id].description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{channel_id}"
        self._attr_name = desc.name

    @property
    def available(self) -> bool:
        """Return True if the channel is present in the latest update."""
        return super().available and self._channel_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return the boolean state of the channel."""
        channel = self.coordinator.data.get(self._channel_id)
        if channel is None or channel.value is None:
            return None
        return bool(channel.value)
