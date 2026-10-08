"""The three lists as to-do entities, so Assist can add to them and a dashboard can tick them.

Weekly chores are ticked per week in the app; here "completed" means done this week.
"""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity

LISTS = ("shopping", "longterm", "weekly")
BASE_FEATURES = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
                 | TodoListEntityFeature.DELETE_TODO_ITEM)


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(SamsasTodoList(entry.runtime_data, name) for name in LISTS)


def _due_text(due: date | datetime | None) -> str | None:
    if due is None:
        return None
    return (due.date() if isinstance(due, datetime) else due).isoformat()


class SamsasTodoList(SamsasEntity, TodoListEntity):
    def __init__(self, coordinator: SamsasCoordinator, name: str) -> None:
        super().__init__(coordinator, name)
        self._list = name
        self._attr_supported_features = BASE_FEATURES
        if name == "longterm":   # the one list where a deadline means something
            self._attr_supported_features |= TodoListEntityFeature.SET_DUE_DATE_ON_ITEM

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=str(item["id"]), summary=item["text"],
                status=TodoItemStatus.COMPLETED if item["done"] else TodoItemStatus.NEEDS_ACTION,
                due=date.fromisoformat(item["due"]) if item.get("due") else None,
            )
            for item in self.coordinator.data["lists"][self._list]
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self.coordinator.api.add_item(self._list, item.summary, due=_due_text(item.due))
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        fields = {"text": item.summary, "done": item.status == TodoItemStatus.COMPLETED}
        if self._list == "weekly":
            fields["day"] = dt_util.now().date().isoformat()
        if self._list == "longterm":
            fields["due"] = _due_text(item.due)
        await self.coordinator.api.update_item(int(item.uid), **fields)
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.api.delete_item(int(uid))
        await self.coordinator.async_request_refresh()
