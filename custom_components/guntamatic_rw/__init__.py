"""The Guntamatic (read/write) integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GuntamaticClient
from .const import PLATFORMS
from .coordinator import GuntamaticConfigEntry, GuntamaticDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Set up Guntamatic from a config entry."""
    session = async_get_clientsession(hass)
    client = GuntamaticClient(session, entry.data[CONF_HOST], entry.data[CONF_API_KEY])

    coordinator = GuntamaticDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GuntamaticConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: GuntamaticConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
