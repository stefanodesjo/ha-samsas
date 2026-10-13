"""The week as a calendar entity: the family's events, the address notices, the
deadlines on Egna listor, the days worth knowing (birthdays, anniversaries,
holidays, theme days) and the weeks a child with two homes is here."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import SamsasError
from .const import KIND_EMOJI, NOTICE_EMOJI, TIMED_MINUTES
from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SamsasCalendar(entry.runtime_data)])


def _who(coordinator: SamsasCoordinator, event: dict) -> str:
    """The adults on it, as the feed says it: "Alva och Bo", or "ingen än".
    Older servers send only owner_id; the child is in the title already."""
    ids = event.get("members") or ([event["owner_id"]] if event.get("owner_id") else [])
    names = [n for n in (coordinator.member_name(i) for i in ids) if n]
    if len(names) > 1:
        return ", ".join(names[:-1]) + " och " + names[-1]
    return names[0] if names else "ingen än"


def _at(day: date, clock: str, tz) -> datetime:
    hour, minute = map(int, clock.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def _stays(stays: list[dict]) -> list[CalendarEvent]:
    """The weeks a child is here, as the feed has them: children on the same
    schedule share one entry ("🏠 Ella och Noah hos oss")."""
    periods: dict[tuple[str, str], list[dict]] = {}
    for stay in stays:
        periods.setdefault((stay["start"], stay["end"]), []).append(stay)
    out = []
    for (start, end), kids in sorted(periods.items()):
        names = [k["name"] for k in kids]
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " och " + names[-1]
        symbol = (kids[0].get("emoji") or "🏠") if len(kids) == 1 else "🏠"
        out.append(CalendarEvent(start=date.fromisoformat(start), end=date.fromisoformat(end), summary=f"{symbol} {who} hos oss",
                                 uid=f"stay-{start}-{'-'.join(str(k['kid_id']) for k in kids)}"))
    return out


def to_calendar_events(coordinator: SamsasCoordinator, events: list[dict], notices: list[dict],
                       days: list[dict] | None = None, stays: list[dict] | None = None) -> list[CalendarEvent]:
    """Summaries read like the app's own feed: the event's emoji (or its kind's), title, and who.
    Like the feed, a child's event in a week the child is at the other home is left out."""
    out: list[CalendarEvent] = _stays(stays or [])
    tz = dt_util.get_default_time_zone()
    for event in events:
        if event.get("away"):
            continue
        day = date.fromisoformat(event["day"])
        last = date.fromisoformat(event["end_day"]) if event.get("end_day") else day
        symbol = event.get("emoji") or KIND_EMOJI.get(event["kind"], "")
        summary = f"{symbol} {event['title']}".strip() + f" – {_who(coordinator, event)}"
        uid = f"event-{event['id']}"
        if event["time"]:
            start = _at(day, event["time"], tz)
            end = _at(last, event["end_time"], tz) if event.get("end_time") else start + timedelta(minutes=TIMED_MINUTES)
            if end <= start:
                end = start + timedelta(minutes=TIMED_MINUTES)
            out.append(CalendarEvent(start=start, end=end, summary=summary, uid=uid))
        else:
            out.append(CalendarEvent(start=day, end=last + timedelta(days=1), summary=summary, uid=uid))
    for notice in notices + (days or []):
        day = date.fromisoformat(notice["day"])
        summary = f"{NOTICE_EMOJI.get(notice['kind'], '')} {notice['title']}".strip()
        out.append(CalendarEvent(start=day, end=day + timedelta(days=1), summary=summary,
                                 uid=f"{notice['kind']}-{notice['day']}-{notice['title']}"))
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
        return [e for e in to_calendar_events(self.coordinator, data["events"], data["notices"], data.get("days"), data.get("stays"))
                if e.end_datetime_local > start_date and e.start_datetime_local < end_date]
