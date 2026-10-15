"""The entities the household picked, sent to Samsas for Hem's Huset card.

A value goes when it changes, at most once a minute per entity, so a power
meter that ticks every second does not hammer the app; the last value always
arrives. Every quarter of an hour the whole set goes again, in the order
picked: that is how Samsas knows the house is still there, and how an entity
taken off the list disappears from the card. Only the current value is sent,
never a history.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from .api import SamsasApi, SamsasError
from .const import LOGGER

SEND_EVERY = timedelta(minutes=1)       # per entity, at most
FULL_SYNC = timedelta(minutes=15)
NAME_MAX = 60


def payload(state: State) -> dict[str, Any]:
    """One entity as Samsas takes it (/hass/v1/entities)."""
    return {
        "entity_id": state.entity_id,
        "name": (state.name or state.entity_id)[:NAME_MAX],
        "state": state.state[:255],
        "unit": state.attributes.get("unit_of_measurement"),
        "device_class": state.attributes.get("device_class"),
        "changed_at": state.last_changed.isoformat(),
    }


class HouseShare:
    def __init__(self, hass: HomeAssistant, api: SamsasApi, entity_ids: list[str]) -> None:
        self.hass, self.api, self.entity_ids = hass, api, list(entity_ids)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._sent: dict[str, datetime] = {}
        self._waiting: dict[str, CALLBACK_TYPE] = {}

    async def start(self) -> None:
        if self.entity_ids:
            self._unsubs.append(async_track_state_change_event(self.hass, self.entity_ids, self._changed))
        self._unsubs.append(async_track_time_interval(self.hass, self._full, FULL_SYNC))
        await self._full()

    @callback
    def stop(self) -> None:
        for unsub in [*self._unsubs, *self._waiting.values()]:
            unsub()
        self._unsubs.clear()
        self._waiting.clear()

    async def _full(self, _now: datetime | None = None) -> None:
        states = [s for e in self.entity_ids if (s := self.hass.states.get(e)) is not None]
        try:
            await self.api.share_entities([payload(s) for s in states], complete=True)
        except SamsasError as err:
            LOGGER.warning("Could not share the house with Samsas: %s", err)
            return
        now = datetime.now()
        for s in states:
            self._sent[s.entity_id] = now

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        if event.data["new_state"] is None or entity_id in self._waiting:
            return              # removed, or a send is already on its way and will take the newest value
        last = self._sent.get(entity_id)
        wait = 0.0 if last is None else max(0.0, (last + SEND_EVERY - datetime.now()).total_seconds())
        if wait == 0:
            self.hass.async_create_task(self._send(entity_id))
        else:
            self._waiting[entity_id] = async_call_later(self.hass, wait, partial(self._later, entity_id))

    @callback
    def _later(self, entity_id: str, _now: datetime) -> None:
        self._waiting.pop(entity_id, None)
        self.hass.async_create_task(self._send(entity_id))

    async def _send(self, entity_id: str) -> None:
        if (state := self.hass.states.get(entity_id)) is None:
            return
        self._sent[entity_id] = datetime.now()
        try:
            await self.api.share_entities([payload(state)])
        except SamsasError as err:
            LOGGER.debug("Samsas did not take %s: %s", entity_id, err)
