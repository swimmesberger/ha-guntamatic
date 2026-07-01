"""Data update coordinator for the Guntamatic (read/write) integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    DaqDescription,
    GuntamaticAuthError,
    GuntamaticClient,
    GuntamaticError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GuntamaticConfigEntry = ConfigEntry[GuntamaticDataUpdateCoordinator]


@dataclass(slots=True)
class ChannelData:
    """A DAQ channel's description together with its latest value."""

    description: DaqDescription
    value: Any


class GuntamaticDataUpdateCoordinator(DataUpdateCoordinator[dict[int, ChannelData]]):
    """Polls the device and caches the (immutable) channel descriptions."""

    config_entry: GuntamaticConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GuntamaticConfigEntry,
        client: GuntamaticClient,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.descriptions: list[DaqDescription] = []

    async def _async_update_data(self) -> dict[int, ChannelData]:
        """Fetch data, (re)loading descriptions when needed."""
        try:
            if not self.descriptions:
                self.descriptions = await self.client.async_get_descriptions()

            values = await self.client.async_get_data()

            # Descriptions are cached; if the array length no longer matches the
            # data (e.g. authorization level or firmware changed), refetch BOTH so
            # they come from the same snapshot. Values and descriptions are only
            # positionally aligned within one snapshot, so a partial refetch could
            # silently map values to the wrong channel.
            if len(values) != len(self.descriptions):
                _LOGGER.debug(
                    "DAQ length mismatch (%s values vs %s descriptions); refreshing",
                    len(values),
                    len(self.descriptions),
                )
                self.descriptions = await self.client.async_get_descriptions()
                values = await self.client.async_get_data()
                if len(values) != len(self.descriptions):
                    raise UpdateFailed(
                        f"DAQ description/value length mismatch "
                        f"({len(values)} values vs {len(self.descriptions)} descriptions)"
                    )

            return {
                desc.id: ChannelData(description=desc, value=value)
                for desc, value in zip(self.descriptions, values)
            }
        except GuntamaticAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GuntamaticError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_parameter(self, syn: str, value: int) -> None:
        """Write a parameter and refresh so sensors reflect the change quickly."""
        await self.client.async_set_parameter(syn, value)
        await self.async_request_refresh()
