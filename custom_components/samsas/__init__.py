"""Samsas — the family's week, lists and dinner, in the house."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SamsasApi
from .const import CONF_TOKEN, CONF_URL
from .coordinator import SamsasConfigEntry, SamsasCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry) -> bool:
    api = SamsasApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = SamsasCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SamsasConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
