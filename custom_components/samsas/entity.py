"""What every Samsas entity shares: the coordinator and one device per household."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SamsasCoordinator


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
