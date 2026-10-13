"""The lists as to-do entities, so Assist can add to them and a dashboard can tick them.

Weekly chores are ticked per week in the app; here "completed" means done this
week. The adults' weekly list is "Varje vecka"; each child has their own chore
list, so a tablet in the child's room can tick them (a tick earns the chore's
points, as in the app). "longterm" is "Att göra", the first of Egna listor;
each list the household makes itself there (a packing list) is one more.
A shopping row from the week's menu says which dishes it is for.
"""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SamsasConfigEntry, SamsasCoordinator
from .entity import SamsasEntity, SamsasKidEntity, add_per_item, add_per_kid

LISTS = ("shopping", "longterm", "weekly")
BASE_FEATURES = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
                 | TodoListEntityFeature.DELETE_TODO_ITEM)


async def async_setup_entry(hass: HomeAssistant, entry: SamsasConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(SamsasTodoList(entry.runtime_data, name) for name in LISTS)
    # the children's chores: only our own children (a shared child's chores live in the other home)
    add_per_kid(entry, async_add_entities,
                lambda coordinator, kid: [] if kid.get("followed") else [SamsasChoreList(coordinator, kid)])
    # Egna listor beyond "Att göra"; older servers send none
    add_per_item(entry, async_add_entities, lambda data: data.get("custom_lists") or [],
                 lambda coordinator, lst: [SamsasCustomList(coordinator, lst)])


def _todo(item: dict) -> TodoItem:
    return TodoItem(
        uid=str(item["id"]), summary=item["text"],
        status=TodoItemStatus.COMPLETED if item["done"] else TodoItemStatus.NEEDS_ACTION,
        due=date.fromisoformat(item["due"]) if item.get("due") else None,
        # the shopping list: the dishes a row from the menu is for
        description=", ".join(item["dishes"]) if item.get("dishes") else None,
    )


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
        items = self.coordinator.data["lists"][self._list]
        if self._list == "weekly":
            items = [i for i in items if i.get("kid_id") is None]       # the children's chores have lists of their own
        return [_todo(item) for item in items]

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


class SamsasCustomList(SamsasEntity, TodoListEntity):
    """One of the household's own lists. Named as in the app, and renamed with it;
    a list deleted in the app leaves the entity unavailable."""

    _attr_icon = "mdi:format-list-checks"
    _attr_supported_features = BASE_FEATURES | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM

    def __init__(self, coordinator: SamsasCoordinator, lst: dict) -> None:
        super().__init__(coordinator, "custom_list")
        self.list_id = lst["id"]
        self._attr_translation_key = None
        self._attr_unique_id = f"{coordinator.household}-custom_list-{lst['id']}"
        self._last_name = lst["name"]

    @property
    def list(self) -> dict | None:
        return next((c for c in self.coordinator.data.get("custom_lists") or [] if c["id"] == self.list_id), None)

    @property
    def name(self) -> str:
        if lst := self.list:
            self._last_name = lst["name"]
        return self._last_name

    @property
    def available(self) -> bool:
        return super().available and self.list is not None

    @property
    def todo_items(self) -> list[TodoItem]:
        return [_todo(item) for item in (self.list or {}).get("items", [])]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self.coordinator.api.add_custom_item(self.list_id, item.summary, due=_due_text(item.due))
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        await self.coordinator.api.update_item(int(item.uid), text=item.summary,
                                               done=item.status == TodoItemStatus.COMPLETED, due=_due_text(item.due))
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.api.delete_item(int(uid))
        await self.coordinator.async_request_refresh()


class SamsasChoreList(SamsasKidEntity, TodoListEntity):
    """A child's chores this week. Ticking and renaming only: what a chore is
    worth and adding new ones stay with the parents, in the app."""

    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: SamsasCoordinator, kid: dict) -> None:
        super().__init__(coordinator, "kid_chores", kid)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [_todo(item) for item in self.coordinator.data["lists"]["weekly"] if item.get("kid_id") == self.kid_id]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        await self.coordinator.api.update_item(int(item.uid), text=item.summary,
                                               done=item.status == TodoItemStatus.COMPLETED,
                                               day=dt_util.now().date().isoformat())
        await self.coordinator.async_request_refresh()
