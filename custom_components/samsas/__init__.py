"""Samsas — the family's week, lists and dinner, in the house; and the house in Samsas."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import SamsasApi, SamsasError
from .const import (ATTR_CONFIG_ENTRY, ATTR_MEMBER, ATTR_MESSAGE, ATTR_TEXT, ATTR_TITLE, ATTR_TO, ATTR_URL, CONF_SHARED,
                    CONF_TOKEN, CONF_URL, DOMAIN, SERVICE_IMPORT_RECIPE, SERVICE_NOTIFY)
from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .share import HouseShare

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

IMPORT_SCHEMA = vol.All(
    vol.Schema({
        vol.Optional(ATTR_URL): cv.string,
        vol.Optional(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_MEMBER): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
    }),
    cv.has_at_least_one_key(ATTR_URL, ATTR_TEXT),
)
NOTIFY_SCHEMA = vol.Schema({
    vol.Required(ATTR_MESSAGE): vol.All(cv.string, vol.Length(min=1, max=240)),
    vol.Optional(ATTR_TITLE): vol.All(cv.string, vol.Length(max=60)),
    vol.Optional(ATTR_TO): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """The services. Registered once, whatever the number of households."""

    async def import_recipe(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY))
        member = None
        if name := call.data.get(ATTR_MEMBER):
            member = coordinator.member_id(name)
            if member is None:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_member",
                                             translation_placeholders={"name": name})
        try:
            saved = await coordinator.api.import_recipe(call.data.get(ATTR_URL), call.data.get(ATTR_TEXT), member)
        except SamsasError as err:
            if err.status == 402:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="needs_plus") from err
            raise HomeAssistantError(str(err)) from err
        return {"title": saved["title"], "kind": saved["kind"], "where": saved["where"]}

    hass.services.async_register(DOMAIN, SERVICE_IMPORT_RECIPE, import_recipe, schema=IMPORT_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)

    async def notify(call: ServiceCall) -> None:
        """A push to the adults in Samsas, in your own words (Samsas Plus)."""
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY))
        members = None
        if names := call.data.get(ATTR_TO):
            members = []
            for name in names:
                if (member := coordinator.member_id(name)) is None:
                    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_member",
                                                 translation_placeholders={"name": name})
                members.append(member)
        try:
            await coordinator.api.notify(call.data[ATTR_MESSAGE], call.data.get(ATTR_TITLE), members)
        except SamsasError as err:
            if err.status == 402:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="notify_needs_plus") from err
            if err.status == 429:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="too_many_notifications") from err
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(DOMAIN, SERVICE_NOTIFY, notify, schema=NOTIFY_SCHEMA)
    return True


def _coordinator(hass: HomeAssistant, entry_id: str | None) -> SamsasCoordinator:
    """The household the call is about: the one named, or the only one set up."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="which_household")
    return entries[0].runtime_data


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry) -> bool:
    api = SamsasApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = SamsasCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # the house in Samsas: only once entities have been picked (an empty pick clears the card)
    if CONF_SHARED in entry.options:
        coordinator.share = HouseShare(hass, api, entry.options[CONF_SHARED])
        await coordinator.share.start()
        entry.async_on_unload(coordinator.share.stop)
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def _options_changed(hass: HomeAssistant, entry: SamsasConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SamsasConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
