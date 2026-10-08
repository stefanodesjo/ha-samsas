"""Tonight's dinner, the next pickup, and the address notices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import PICKUP_KINDS
from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity


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
)


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(SamsasSensor(entry.runtime_data, description) for description in SENSORS)


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
