"""Config and options flow for the Guntamatic (read/write) integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers import selector

from .api import GuntamaticAuthError, GuntamaticClient, GuntamaticError
from .const import (
    BOILER_SYNONYM_K,
    BOILER_SYNONYM_PK,
    CONF_BOILER_SYNONYM,
    CONF_HEATING_CIRCUITS,
    CONF_HOT_WATER_CIRCUITS,
    DEFAULT_BOILER_SYNONYM,
    DEFAULT_HEATING_CIRCUITS,
    DEFAULT_HOT_WATER_CIRCUITS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_HEATING_CIRCUITS,
    MAX_HOT_WATER_CIRCUITS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class GuntamaticConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Guntamatic."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial (manual) step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            api_key = user_input.get(CONF_API_KEY, "").strip()
            error = await self._async_validate(host, api_key)
            if error is None:
                # Reconcile by host across both the manual and DHCP flows, so the
                # same physical device is never added twice (their unique_id
                # namespaces — host vs MAC — otherwise never collide).
                self._async_abort_entries_match({CONF_HOST: host})
                if self.unique_id is None:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=host,
                    data={CONF_HOST: host, CONF_API_KEY: api_key},
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host or ""): str,
                vol.Optional(CONF_API_KEY, default=""): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via DHCP (hostname kessel* / MAC 0024BD*)."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self._host = discovery_info.ip
        self.context["title_placeholders"] = {
            "name": discovery_info.hostname or discovery_info.ip
        }
        # The device address is known, but the API key still has to be entered.
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the API key becomes invalid."""
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key and update the existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await self._async_validate(self._host or "", api_key)
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: api_key},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"host": self._host or ""},
            errors=errors,
        )

    async def _async_validate(self, host: str, api_key: str) -> str | None:
        """Return an error key, or None when the connection is valid."""
        client = GuntamaticClient(async_get_clientsession(self.hass), host, api_key)
        try:
            await client.async_get_descriptions()
            await client.async_get_data()
        except GuntamaticAuthError:
            return "invalid_auth" if api_key else "key_required"
        except GuntamaticError:
            return "cannot_connect"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Create the options flow."""
        return GuntamaticOptionsFlow()


class GuntamaticOptionsFlow(OptionsFlow):
    """Handle options for the integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_HEATING_CIRCUITS,
                    default=options.get(
                        CONF_HEATING_CIRCUITS, DEFAULT_HEATING_CIRCUITS
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=MAX_HEATING_CIRCUITS,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_HOT_WATER_CIRCUITS,
                    default=options.get(
                        CONF_HOT_WATER_CIRCUITS, DEFAULT_HOT_WATER_CIRCUITS
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=MAX_HOT_WATER_CIRCUITS,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_BOILER_SYNONYM,
                    default=options.get(
                        CONF_BOILER_SYNONYM, DEFAULT_BOILER_SYNONYM
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=BOILER_SYNONYM_PK,
                                label="Powerchip / Powercorn / Biocom / Pro (PK002)",
                            ),
                            selector.SelectOptionDict(
                                value=BOILER_SYNONYM_K,
                                label="Therm / Biostar (K0010)",
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
