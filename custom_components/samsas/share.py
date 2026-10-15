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

from homeassistant.components import persistent_notification
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from .api import SamsasApi, SamsasError
from .const import LOGGER

NOTICE_ID = "samsas_house_plus"
SEND_EVERY = timedelta(minutes=1)       # per entity, at most
FULL_SYNC = timedelta(minutes=15)
NAME_MAX = 60


def name_of(hass: HomeAssistant, state: State) -> str:
    """What the card calls it: the household's own name for it if they renamed it,
    otherwise the entity's own ("Elpris", not "Tibber Pulse Storgatan 1 Elpris");
    the full friendly name when that is all there is."""
    entry = er.async_get(hass).async_get(state.entity_id)
    if entry is not None:
        if entry.name:
            return entry.name
        if entry.has_entity_name and entry.original_name:
            return entry.original_name
    return state.name or state.entity_id


def payload(hass: HomeAssistant, state: State) -> dict[str, Any]:
    """One entity as Samsas takes it (/hass/v1/entities)."""
    return {
        "entity_id": state.entity_id,
        "name": name_of(hass, state)[:NAME_MAX],
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
            answer = await self.api.share_entities([payload(self.hass, s) for s in states], complete=True)
        except SamsasError as err:
            LOGGER.warning("Could not share the house with Samsas: %s", err)
            return
        self._tell_about_plus(answer)
        now = datetime.now()
        for s in states:
            self._sent[s.entity_id] = now

    @callback
    def _tell_about_plus(self, answer: dict) -> None:
        """Without Samsas Plus the card shows the first two picked: say so here,
        where they were picked, until it no longer applies."""
        hidden, limit = answer.get("hidden", 0), answer.get("limit")
        if not hidden:
            persistent_notification.async_dismiss(self.hass, NOTICE_ID)
            return
        swedish = (self.hass.config.language or "").startswith("sv")
        message = (f"Samsas visar {limit} av {limit + hidden} värden på kortet Huset. Resten visas med Samsas Plus, som ni skaffar i appen."
                   if swedish else
                   f"Samsas shows {limit} of {limit + hidden} values on the House card. The rest show with Samsas Plus, which you get in the app.")
        persistent_notification.async_create(self.hass, message, title="Samsas", notification_id=NOTICE_ID)

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
            await self.api.share_entities([payload(self.hass, state)])
        except SamsasError as err:
            LOGGER.debug("Samsas did not take %s: %s", entity_id, err)
