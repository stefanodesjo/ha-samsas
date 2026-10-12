"""What every Samsas entity shares: the coordinator and one device per household."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SamsasConfigEntry, SamsasCoordinator


class SamsasEntity(CoordinatorEntity[SamsasCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SamsasCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.household}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.household)},
            name="Samsas",
            manufacturer="Samsas",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.api.base,
        )


class SamsasKidEntity(SamsasEntity):
    """One child's entity: "Ellas poäng". The child's name is part of the entity
    name; one who is removed in the app leaves the entity unavailable."""

    def __init__(self, coordinator: SamsasCoordinator, key: str, kid: dict) -> None:
        super().__init__(coordinator, key)
        self.kid_id = kid["id"]
        self._attr_unique_id = f"{coordinator.household}-{key}-{kid['id']}"
        self._attr_translation_placeholders = {"kid": kid["name"]}

    @property
    def kid(self) -> dict | None:
        return self.coordinator.kid(self.kid_id)

    @property
    def available(self) -> bool:
        return super().available and self.kid is not None


def add_per_kid(entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback,
                make: Callable[[SamsasCoordinator, dict], Iterable[Entity]]) -> None:
    """Entities for each child now, and for a child added in the app later."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def add_new() -> None:
        entities: list[Entity] = []
        for kid in coordinator.data["kids"]:
            if kid["id"] not in known:
                known.add(kid["id"])
                entities.extend(make(coordinator, kid))
        if entities:
            async_add_entities(entities)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))
