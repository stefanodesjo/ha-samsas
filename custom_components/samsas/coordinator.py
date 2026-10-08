"""One poll of /hass/v1/state feeds every entity."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SamsasApi, SamsasAuthError, SamsasError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type SamsasConfigEntry = ConfigEntry[SamsasCoordinator]


class SamsasCoordinator(DataUpdateCoordinator[dict]):
    config_entry: SamsasConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SamsasConfigEntry, api: SamsasApi) -> None:
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            # "today" is the house's local date, like the phones send theirs
            return await self.api.state(dt_util.now().date())
        except SamsasAuthError as err:
            raise ConfigEntryAuthFailed from err
        except SamsasError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def household(self) -> str:
        return str(self.data["household"])

    def member_name(self, member_id: int | None) -> str | None:
        return next((m["name"] for m in self.data["members"] if m["id"] == member_id), None)

    def kid_name(self, kid_id: int | None) -> str | None:
        return next((k["name"] for k in self.data["kids"] if k["id"] == kid_id), None)
