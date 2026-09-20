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
    Parameter,
    infer_keyless_type,
)
from .const import BURNER_OUTPUT_CHANNEL_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GuntamaticConfigEntry = ConfigEntry[GuntamaticDataUpdateCoordinator]


@dataclass(slots=True)
class ChannelData:
    """A DAQ channel's description together with its latest value."""

    description: DaqDescription
    value: Any


class GuntamaticDataUpdateCoordinator(DataUpdateCoordinator[dict[int, ChannelData]]):
    """Polls the device: DAQ channels + par.cgi parameters."""

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
        self.parameters: dict[str, Parameter] = {}

    @property
    def has_key(self) -> bool:
        """Whether an API key is configured (unlocks the full DAQ set + control)."""
        return self.client.has_key

    def channel_value_by_name(self, name: str) -> Any:
        """Return the latest value of the first channel with this exact name.

        Channel ids differ between the keyed and keyless endpoints, so lookups
        that must work in both modes have to go via the description name.
        """
        for channel in (self.data or {}).values():
            if channel.description.name.strip() == name:
                return channel.value
        return None

    @property
    def is_burning(self) -> bool | None:
        """Whether the burner is currently producing output.

        Returns None when the output channel is absent or unparseable, so that
        callers can tell "not burning" apart from "cannot tell".
        """
        raw = self.channel_value_by_name(BURNER_OUTPUT_CHANNEL_NAME)
        if raw is None:
            return None
        try:
            return float(str(raw).strip()) > 0
        except (TypeError, ValueError):
            return None

    async def _async_update_data(self) -> dict[int, ChannelData]:
        """Fetch DAQ data (+ par.cgi), (re)loading descriptions when needed."""
        try:
            if not self.descriptions:
                self.descriptions = await self.client.async_get_descriptions()

            values = await self.client.async_get_data()

            # Descriptions are cached; if the array length no longer matches the
            # data, refetch BOTH so they come from the same snapshot (values and
            # descriptions are only positionally aligned within one snapshot).
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

            # Keyless descriptions carry no type; infer it once from unit/value.
            for desc, value in zip(self.descriptions, values):
                if desc.type == "":
                    desc.type = infer_keyless_type(value, desc.unit)

            channels = {
                desc.id: ChannelData(description=desc, value=value)
                for desc, value in zip(self.descriptions, values)
            }
        except GuntamaticAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GuntamaticError as err:
            raise UpdateFailed(str(err)) from err

        # par.cgi is keyless and rarely changes; failure here must not break the
        # DAQ update, so keep the previous parameters on error.
        try:
            self.parameters = await self.client.async_get_parameters()
        except GuntamaticError as err:
            _LOGGER.debug("par.cgi fetch failed: %s", err)

        return channels

    async def async_set_parameter(self, syn: str, value: int) -> None:
        """Write a parameter and refresh so entities reflect the change quickly."""
        await self.client.async_set_parameter(syn, value)
        await self.async_request_refresh()
