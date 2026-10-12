"""Tonight's dinner, the next pickup, the address notices, what is counted down
to, the name day, swap requests, the weekly list, and per child where they are
and their points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import PICKUP_KINDS
from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity, SamsasKidEntity, add_per_kid


def next_event(coordinator: SamsasCoordinator, kinds: tuple[str, ...], now: datetime) -> dict | None:
    """The first event of those kinds that has not started yet. Whole-day events count all day."""
    today, clock = now.date().isoformat(), now.strftime("%H:%M")
    for event in coordinator.data["events"]:
        if event["kind"] not in kinds:
            continue
        if event["day"] > today or (event["day"] == today and (not event["time"] or event["time"] >= clock)):
            return event
    return None


def next_notice(coordinator: SamsasCoordinator, kind: str) -> dict | None:
    return next((n for n in coordinator.data["notices"] if n["kind"] == kind), None)


def _pickup(coordinator: SamsasCoordinator) -> str | None:
    event = next_event(coordinator, PICKUP_KINDS, dt_util.now())
    return event["title"] if event else None


def _pickup_attributes(coordinator: SamsasCoordinator) -> dict[str, Any]:
    event = next_event(coordinator, PICKUP_KINDS, dt_util.now())
    if not event:
        return {}
    return {"day": event["day"], "time": event["time"], "kind": event["kind"],
            "who": coordinator.member_name(event["owner_id"]), "kid": coordinator.kid_name(event["kid_id"])}


def _notice_day(kind: str) -> Callable[[SamsasCoordinator], date | None]:
    def value(coordinator: SamsasCoordinator) -> date | None:
        notice = next_notice(coordinator, kind)
        return date.fromisoformat(notice["day"]) if notice else None
    return value


def _notice_attributes(kind: str) -> Callable[[SamsasCoordinator], dict[str, Any]]:
    def value(coordinator: SamsasCoordinator) -> dict[str, Any]:
        notice = next_notice(coordinator, kind)
        return {"title": notice["title"]} if notice else {}
    return value


def _countdown(coordinator: SamsasCoordinator) -> dict | None:
    return next(iter(coordinator.data.get("countdowns") or []), None)


def _countdown_attributes(coordinator: SamsasCoordinator) -> dict[str, Any]:
    first = _countdown(coordinator)
    if not first:
        return {}
    return {"title": first["title"], "emoji": first.get("emoji"), "date": first["day"],
            "upcoming": [{"title": c["title"], "emoji": c.get("emoji"), "date": c["day"], "days": c["days"]}
                         for c in coordinator.data["countdowns"]]}


def _name_day(coordinator: SamsasCoordinator) -> str | None:
    names = (coordinator.data.get("dagar") or {}).get("namnsdag") or []
    return ", ".join(names) or None


def _day_attributes(coordinator: SamsasCoordinator) -> dict[str, Any]:
    dagar = coordinator.data.get("dagar") or {}
    return {"holiday": dagar.get("helgdag"), "flag_day": dagar.get("flaggdag"),
            "red_day": bool(dagar.get("rod_dag")), "theme_day": dagar.get("temadag")}


def _swap_attributes(coordinator: SamsasCoordinator) -> dict[str, Any]:
    return {"requests": [{"title": s["title"], "day": s["day"], "time": s["time"],
                          "from": coordinator.member_name(s["from_id"]), "kid": coordinator.kid_name(s["kid_id"])}
                         for s in coordinator.data.get("swaps") or []]}


def _weekly_left(coordinator: SamsasCoordinator) -> int | None:
    weekly = coordinator.data.get("weekly")
    return weekly["total"] - weekly["done"] if weekly else None


@dataclass(frozen=True, kw_only=True)
class SamsasSensorDescription(SensorEntityDescription):
    value: Callable[[SamsasCoordinator], Any]
    attributes: Callable[[SamsasCoordinator], dict[str, Any]] = lambda coordinator: {}


SENSORS: tuple[SamsasSensorDescription, ...] = (
    SamsasSensorDescription(
        key="dinner", translation_key="dinner", icon="mdi:silverware-fork-knife",
        value=lambda c: c.data["dinner"],
        attributes=lambda c: {"menu": {d["day"]: d["dish"] for d in c.data["menu"]}},
    ),
    SamsasSensorDescription(
        key="next_pickup", translation_key="next_pickup", icon="mdi:car-child-seat",
        value=_pickup, attributes=_pickup_attributes,
    ),
    SamsasSensorDescription(
        key="next_waste", translation_key="next_waste", icon="mdi:trash-can-outline",
        device_class=SensorDeviceClass.DATE, value=_notice_day("waste"), attributes=_notice_attributes("waste"),
    ),
    SamsasSensorDescription(
        key="next_post", translation_key="next_post", icon="mdi:mailbox-outline",
        device_class=SensorDeviceClass.DATE, value=_notice_day("post"),
    ),
    SamsasSensorDescription(
        key="countdown", translation_key="countdown", icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value=lambda c: (_countdown(c) or {}).get("days"), attributes=_countdown_attributes,
    ),
    SamsasSensorDescription(
        key="name_day", translation_key="name_day", icon="mdi:calendar-star",
        value=_name_day, attributes=_day_attributes,
    ),
    SamsasSensorDescription(
        key="swaps", translation_key="swaps", icon="mdi:swap-horizontal",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda c: len(c.data.get("swaps") or []), attributes=_swap_attributes,
    ),
    SamsasSensorDescription(
        key="weekly_left", translation_key="weekly_left", icon="mdi:checkbox-marked-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value=_weekly_left, attributes=lambda c: dict(c.data.get("weekly") or {}),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(SamsasSensor(entry.runtime_data, description) for description in SENSORS)

    def per_kid(coordinator: SamsasCoordinator, kid: dict) -> list[SensorEntity]:
        entities: list[SensorEntity] = []
        if kid.get("custody"):
            entities.append(SamsasCustodySensor(coordinator, kid))
        if not kid.get("followed"):        # points live with the child's own home
            entities.append(SamsasPointsSensor(coordinator, kid))
        return entities

    add_per_kid(entry, async_add_entities, per_kid)


class SamsasSensor(SamsasEntity, SensorEntity):
    entity_description: SamsasSensorDescription

    def __init__(self, coordinator: SamsasCoordinator, description: SamsasSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.entity_description.attributes(self.coordinator)


class SamsasCustodySensor(SamsasKidEntity, SensorEntity):
    """Where a child with shared custody is this period: here, or in the other home."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["here", "away"]
    _attr_icon = "mdi:home-switch-outline"

    def __init__(self, coordinator: SamsasCoordinator, kid: dict) -> None:
        super().__init__(coordinator, "kid_custody", kid)

    @property
    def native_value(self) -> str | None:
        custody = (self.kid or {}).get("custody")
        return None if not custody else "here" if custody["here"] else "away"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        custody = (self.kid or {}).get("custody") or {}
        # `until`: the day the child moves; the app counts it down on Hem the last days before
        return {"other_home": custody.get("other_home"), "since": custody.get("since"), "until": custody.get("until")}


class SamsasPointsSensor(SamsasKidEntity, SensorEntity):
    """A child's points since the last reward, with this week's chores as attributes."""

    _attr_icon = "mdi:star-circle-outline"
    _attr_state_class = SensorStateClass.TOTAL      # the unit ("poäng"/"points") is in the translations

    def __init__(self, coordinator: SamsasCoordinator, kid: dict) -> None:
        super().__init__(coordinator, "kid_points", kid)

    @property
    def native_value(self) -> int | None:
        points = (self.kid or {}).get("points")
        return points["total"] if points else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        kid = self.kid or {}
        chores = kid.get("chores") or {}
        return {"this_week": (kid.get("points") or {}).get("week"),
                "chores_done": chores.get("done"), "chores_total": chores.get("total")}
