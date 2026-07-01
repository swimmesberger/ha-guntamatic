"""Thin async client for the Guntamatic HTTP/CGI web interface.

Two access levels are supported:

* **With API key** (authorization level W1+): the richer JSON endpoints
  ``/ext/daqdesc.cgi`` / ``/ext/daqdata.cgi`` (all channels, typed) and control
  via ``/ext/parset.cgi``.
* **Without API key** (level W0): the keyless plain-text root endpoints
  ``/daqdesc.cgi`` (``Name;Unit`` per line) / ``/daqdata.cgi`` (value per line),
  which expose a reduced, read-only channel set.

``/par.cgi`` is keyless in both cases and exposes the full parameter list
(including the hybrid/heat-pump configuration).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

from .const import NUMERIC_UNITS

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
    type: str  # "float" | "int" | "bool" | "string" | "" (unknown, keyless)
    unit: str | None


@dataclass(slots=True)
class Parameter:
    """A single par.cgi parameter with its current value."""

    par_id: str
    ptype: int
    current: str
    options: list[str] = field(default_factory=list)
    unit: str | None = None

    @property
    def is_enum(self) -> bool:
        """Whether this is a selection parameter (type 6)."""
        return self.ptype == 6

    def display(self) -> str:
        """Return the current value as a human-readable string (enum -> label)."""
        if self.is_enum and self.options:
            try:
                return self.options[int(self.current)]
            except (ValueError, IndexError):
                return self.current
        return self.current

    def numeric(self) -> float | None:
        """Return the current value as a float, or None if not numeric."""
        try:
            return float(self.current)
        except (TypeError, ValueError):
            return None


def infer_keyless_type(value: Any, unit: str | None) -> str:
    """Infer a channel type for the keyless path (no bool: cannot be distinguished)."""
    if unit in NUMERIC_UNITS:
        return "float"
    try:
        float(str(value).strip())
    except (TypeError, ValueError):
        return "string"
    return "float"


class GuntamaticClient:
    """Minimal client around the Guntamatic web/CGI API."""

    def __init__(
        self, session: ClientSession, host: str, api_key: str | None
    ) -> None:
        """Initialize the client with a shared HA aiohttp session."""
        self._session = session
        self._host = host.strip().rstrip("/")
        self._api_key = (api_key or "").strip()

    @property
    def base_url(self) -> str:
        """Return the device base URL."""
        return f"http://{self._host}"

    @property
    def has_key(self) -> bool:
        """Whether an API key is configured."""
        return bool(self._api_key)

    async def _get_bytes(self, path: str) -> bytes:
        """Perform a GET request and return the raw body."""
        url = f"{self.base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(url)
                resp.raise_for_status()
                return await resp.read()
        except (ClientError, asyncio.TimeoutError) as err:
            raise GuntamaticConnectionError(
                f"Error communicating with Guntamatic device at {self._host}: {err}"
            ) from err

    async def _get_json(self, path: str) -> Any:
        """GET and decode JSON, tolerating UTF-8 or ISO-8859-1 payloads."""
        raw = await self._get_bytes(path)
        for encoding in ("utf-8", "latin-1"):
            try:
                return json.loads(raw.decode(encoding))
            except (UnicodeDecodeError, ValueError):
                continue
        raise GuntamaticConnectionError(
            f"Invalid JSON from Guntamatic device at {self._host}"
        )

    async def _get_text(self, path: str) -> str:
        """GET and decode a plain-text (ISO-8859-1) payload."""
        return (await self._get_bytes(path)).decode("latin-1")

    async def async_get_descriptions(self) -> list[DaqDescription]:
        """Fetch DAQ channel descriptions (JSON with key, plain text without)."""
        if self.has_key:
            data = await self._get_json(
                f"/ext/daqdesc.cgi?key={quote(self._api_key)}"
            )
            if not isinstance(data, list):
                raise GuntamaticAuthError(
                    "daqdesc.cgi did not return a list; the API key is likely "
                    "invalid or lacks the required authorization level"
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

        # Keyless: "Name;Unit" per line, positionally aligned with daqdata.
        text = await self._get_text("/daqdesc.cgi")
        keyless: list[DaqDescription] = []
        for idx, line in enumerate(text.splitlines()):
            parts = line.split(";")
            name = parts[0].strip()
            unit = parts[1].strip() if len(parts) > 1 else ""
            keyless.append(
                DaqDescription(id=idx, name=name, type="", unit=(unit or None))
            )
        if not keyless:
            raise GuntamaticAuthError("daqdesc.cgi returned no channels")
        return keyless

    async def async_get_data(self) -> list[Any]:
        """Fetch current DAQ values (positionally aligned to descriptions)."""
        if self.has_key:
            data = await self._get_json(f"/ext/daqdata.cgi?key={quote(self._api_key)}")
            if not isinstance(data, list):
                raise GuntamaticAuthError(
                    "daqdata.cgi did not return a list; the API key is likely "
                    "invalid or lacks the required authorization level"
                )
            return data
        text = await self._get_text("/daqdata.cgi")
        return [line.strip() for line in text.splitlines()]

    async def async_get_parameters(self) -> dict[str, Parameter]:
        """Fetch and parse the par.cgi parameter list (keyless)."""
        text = await self._get_text("/par.cgi")
        params: dict[str, Parameter] = {}
        in_section = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "++Parameterdaten++":
                in_section = True
                continue
            if stripped == "++Parameterdaten_End++":
                break
            if not in_section:
                continue
            parts = line.split(";")
            if len(parts) < 9:
                continue
            par_id = parts[0].strip()
            try:
                ptype = int(parts[1])
            except ValueError:
                continue
            current = parts[2].strip()
            if ptype == 6:  # enum: options follow the name at index 8
                options = [p.strip() for p in parts[9:] if p.strip()]
                params[par_id] = Parameter(par_id, ptype, current, options, None)
            elif ptype in (2, 3):  # numeric: unit at index 6
                unit = parts[6].strip() or None
                params[par_id] = Parameter(par_id, ptype, current, [], unit)
        return params

    async def async_set_parameter(self, syn: str, value: int) -> Any:
        """Set a parameter via parset.cgi and validate the ack/err response."""
        if not self.has_key:
            raise GuntamaticCommandError("An API key is required to control the device")
        data = await self._get_json(
            f"/ext/parset.cgi?syn={quote(syn)}&value={int(value)}&key={quote(self._api_key)}"
        )
        if isinstance(data, dict) and "err" in data:
            raise GuntamaticCommandError(str(data["err"]))
        _LOGGER.debug("parset syn=%s value=%s -> %s", syn, value, data)
        return data
