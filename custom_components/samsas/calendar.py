"""The week as a calendar entity, with the address notices as whole-day entries."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import SamsasError
from .const import KIND_EMOJI, TIMED_MINUTES
from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SamsasCalendar(entry.runtime_data)])


def to_calendar_events(coordinator: SamsasCoordinator, events: list[dict], notices: list[dict]) -> list[CalendarEvent]:
    """Summaries read like the app's own feed: glyph, title, and who takes it."""
    out: list[CalendarEvent] = []
    tz = dt_util.get_default_time_zone()
    for event in events:
        day = date.fromisoformat(event["day"])
        summary = f"{KIND_EMOJI.get(event['kind'], '')} {event['title']}".strip()
        owner = coordinator.member_name(event["owner_id"])
        summary += f" – {owner}" if owner else " – ingen än"
        if event["time"]:
            hour, minute = map(int, event["time"].split(":"))
            start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            out.append(CalendarEvent(start=start, end=start + timedelta(minutes=TIMED_MINUTES),
                                     summary=summary, uid=f"event-{event['id']}"))
        else:
            out.append(CalendarEvent(start=day, end=day + timedelta(days=1), summary=summary, uid=f"event-{event['id']}"))
    for notice in notices:
        day = date.fromisoformat(notice["day"])
        out.append(CalendarEvent(start=day, end=day + timedelta(days=1), summary=notice["title"],
                                 uid=f"{notice['kind']}-{notice['day']}"))
    out.sort(key=lambda e: e.start_datetime_local)
    return out


class SamsasCalendar(SamsasEntity, CalendarEntity):
    def __init__(self, coordinator: SamsasCoordinator) -> None:
        super().__init__(coordinator, "week")

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next entry, from the week the state already carries."""
        now = dt_util.now()
        for entry in to_calendar_events(self.coordinator, self.coordinator.data["events"], self.coordinator.data["notices"]):
            if entry.end_datetime_local > now:
                return entry
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        try:
            data = await self.coordinator.api.events(dt_util.as_local(start_date).date(), dt_util.as_local(end_date).date())
        except SamsasError as err:
            raise HomeAssistantError(str(err)) from err
        return [e for e in to_calendar_events(self.coordinator, data["events"], data["notices"])
                if e.end_datetime_local > start_date and e.start_datetime_local < end_date]
