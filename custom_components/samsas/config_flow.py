"""Set up: the app's address and the token from Vi → Inställningar → Home Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import SamsasApi, SamsasAuthError, SamsasError
from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_URL, default=DEFAULT_URL): str,
    vol.Required(CONF_TOKEN): str,
})
TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


async def _probe(hass: HomeAssistant, url: str, token: str) -> dict:
    """One real call; the household id it returns is the entry's identity."""
    return await SamsasApi(async_get_clientsession(hass), url, token).state(dt_util.now().date())


class SamsasConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                state = await _probe(self.hass, user_input[CONF_URL], user_input[CONF_TOKEN])
            except SamsasAuthError:
                errors["base"] = "invalid_auth"
            except SamsasError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(state["household"]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Samsas", data=user_input)
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """The token was rotated in the app; ask for the new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                state = await _probe(self.hass, entry.data[CONF_URL], user_input[CONF_TOKEN])
            except SamsasAuthError:
                errors["base"] = "invalid_auth"
            except SamsasError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(state["household"]))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=TOKEN_SCHEMA, errors=errors)
