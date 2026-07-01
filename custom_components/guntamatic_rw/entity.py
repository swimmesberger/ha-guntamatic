"""Base entity for the Guntamatic (read/write) integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER
from .coordinator import GuntamaticDataUpdateCoordinator


class GuntamaticEntity(CoordinatorEntity[GuntamaticDataUpdateCoordinator]):
    """Common base class wiring entities to the single device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GuntamaticDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.title or DEFAULT_NAME,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
