"""Thin async client for the Guntamatic HTTP/CGI web interface.

Mirrors the endpoints used by the `guntamatic-web` Rust crate:
  * GET /ext/daqdesc.cgi?key=<key>  -> [{"id","name","type","unit"}, ...]
  * GET /ext/daqdata.cgi?key=<key>  -> [<value>, ...]  (positional, aligned to daqdesc)
  * GET /ext/parset.cgi?syn=<syn>&value=<v>&key=<key> -> {"ack": ...} | {"err": ...}

All endpoints require an API key with at least authorization level W1 (which also
permits the external/parameter commands). See docs/WEB-MODBUS-Schnittstelle_DE.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT: int = 10


class GuntamaticError(Exception):
    """Base error for the Guntamatic client."""


class GuntamaticConnectionError(GuntamaticError):
    """Raised when the device cannot be reached."""


class GuntamaticAuthError(GuntamaticError):
    """Raised when the API key is missing/insufficient (no data returned)."""


class GuntamaticCommandError(GuntamaticError):
    """Raised when the device rejects a parameter-set command."""


@dataclass(slots=True)
class DaqDescription:
    """Metadata describing a single DAQ channel."""

    id: int
    name: str
    type: str
    unit: str | None


class GuntamaticClient:
    """Minimal client around the Guntamatic web/CGI API."""

    def __init__(self, session: ClientSession, host: str, api_key: str) -> None:
        """Initialize the client with a shared HA aiohttp session."""
        self._session = session
        self._host = host.strip().rstrip("/")
        self._api_key = api_key

    @property
    def base_url(self) -> str:
        """Return the device base URL."""
        return f"http://{self._host}"

    async def _get_json(self, path: str) -> Any:
        """Perform a GET request and return the decoded JSON payload."""
        url = f"{self.base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(url)
                resp.raise_for_status()
                # The device may serve JSON with a non-JSON content-type header,
                # so disable aiohttp's content-type check.
                return await resp.json(content_type=None)
        except (ClientError, asyncio.TimeoutError) as err:
            raise GuntamaticConnectionError(
                f"Error communicating with Guntamatic device at {self._host}: {err}"
            ) from err
        except ValueError as err:  # invalid JSON
            raise GuntamaticConnectionError(
                f"Invalid response from Guntamatic device at {self._host}: {err}"
            ) from err

    async def async_get_descriptions(self) -> list[DaqDescription]:
        """Fetch the DAQ channel descriptions."""
        data = await self._get_json(f"/ext/daqdesc.cgi?key={quote(self._api_key)}")
        if not isinstance(data, list):
            raise GuntamaticAuthError(
                "daqdesc.cgi did not return a list; the API key is likely invalid "
                "or lacks the required authorization level"
            )
        descriptions: list[DaqDescription] = []
        for entry in data:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            unit = entry.get("unit")
            descriptions.append(
                DaqDescription(
                    id=int(entry["id"]),
                    name=str(entry.get("name", f"channel_{entry['id']}")),
                    type=str(entry.get("type", "string")).lower(),
                    unit=(str(unit).strip() or None) if unit is not None else None,
                )
            )
        return descriptions

    async def async_get_data(self) -> list[Any]:
        """Fetch the current DAQ values (positionally aligned to descriptions)."""
        data = await self._get_json(f"/ext/daqdata.cgi?key={quote(self._api_key)}")
        if not isinstance(data, list):
            raise GuntamaticAuthError(
                "daqdata.cgi did not return a list; the API key is likely invalid "
                "or lacks the required authorization level"
            )
        return data

    async def async_set_parameter(self, syn: str, value: int) -> Any:
        """Set a parameter via parset.cgi and validate the ack/err response."""
        data = await self._get_json(
            f"/ext/parset.cgi?syn={quote(syn)}&value={int(value)}&key={quote(self._api_key)}"
        )
        if isinstance(data, dict) and "err" in data:
            raise GuntamaticCommandError(str(data["err"]))
        _LOGGER.debug("parset syn=%s value=%s -> %s", syn, value, data)
        return data
