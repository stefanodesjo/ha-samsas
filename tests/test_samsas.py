"""The component against a faked /hass/v1: setup, the entities, and writes to the lists."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsas.api import SamsasAuthError, SamsasError
from custom_components.samsas.const import DOMAIN

TODAY = date.today()


def state_payload() -> dict:
    day = TODAY.isoformat()
    monday = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    return {
        "household": 7, "day": day, "week": monday,
        "members": [{"id": 1, "name": "Alva", "emoji": "🦊"}, {"id": 2, "name": "Bo", "emoji": "🐻"}],
        "kids": [{"id": 3, "name": "Ella", "emoji": "👧"}],
        "events": [
            {"id": 10, "day": day, "time": "07:45", "title": "Lämning Ella", "kind": "lamna", "kid_id": 3, "owner_id": 1},
            {"id": 11, "day": day, "time": "23:59", "title": "Hämtning Ella", "kind": "hamta", "kid_id": 3, "owner_id": 2},
            {"id": 12, "day": (TODAY + timedelta(days=1)).isoformat(), "time": None, "title": "Kalas", "kind": "aktivitet", "kid_id": None, "owner_id": None},
        ],
        "dinner": "Tacos",
        "menu": [{"day": monday, "dish": "Tacos"}],
        "lists": {
            "weekly": [{"id": 20, "text": "Dammsuga", "owner_id": None, "kid_id": None, "done": False}],
            "longterm": [{"id": 21, "text": "Måla om hallen", "owner_id": None, "done": False, "due": "2026-12-01"}],
            "shopping": [{"id": 22, "text": "Mjölk", "owner_id": None, "done": False, "due": None},
                         {"id": 23, "text": "Smör", "owner_id": None, "done": True, "due": None}],
        },
        "notices": [{"day": (TODAY + timedelta(days=2)).isoformat(), "kind": "waste", "title": "Sophämtning: Restavfall"}],
    }


@pytest.fixture
def api():
    with patch("custom_components.samsas.api.SamsasApi.state", new_callable=AsyncMock, return_value=state_payload()) as state, \
         patch("custom_components.samsas.api.SamsasApi.events", new_callable=AsyncMock) as events, \
         patch("custom_components.samsas.api.SamsasApi.add_item", new_callable=AsyncMock, return_value={"ok": True, "id": 99}) as add, \
         patch("custom_components.samsas.api.SamsasApi.update_item", new_callable=AsyncMock, return_value={"ok": True}) as update, \
         patch("custom_components.samsas.api.SamsasApi.delete_item", new_callable=AsyncMock, return_value={"ok": True}) as delete:
        payload = state_payload()
        events.return_value = {"events": payload["events"], "notices": payload["notices"]}
        yield {"state": state, "events": events, "add": add, "update": update, "delete": delete}


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Samsas", unique_id="7",
                            data={"url": "https://samsas.test", "token": "secret"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_checks_the_token_and_keys_the_entry_on_the_household(hass: HomeAssistant, api):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form" and result["errors"] == {}

    api["state"].side_effect = SamsasAuthError()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "https://samsas.test", "token": "wrong"})
    assert result["type"] == "form" and result["errors"] == {"base": "invalid_auth"}

    api["state"].side_effect = SamsasError()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "https://nowhere.test", "token": "x"})
    assert result["errors"] == {"base": "cannot_connect"}

    api["state"].side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "https://samsas.test/", "token": "secret"})
    assert result["type"] == "create_entry" and result["title"] == "Samsas"
    assert result["result"].unique_id == "7"
    await hass.async_block_till_done()

    # the same household a second time is a no-op
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "https://samsas.test", "token": "secret"})
    assert result["type"] == "abort" and result["reason"] == "already_configured"


async def test_entities_show_the_house(hass: HomeAssistant, api, freezer):
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to(f"{TODAY}T12:00:00+00:00")
    await setup_entry(hass)
    assert hass.states.get("sensor.samsas_dinner_tonight").state == "Tacos"
    pickup = hass.states.get("sensor.samsas_next_pickup")
    assert pickup.state == "Hämtning Ella"          # the morning drop-off has passed; 23:59 has not
    assert pickup.attributes["who"] == "Bo" and pickup.attributes["kid"] == "Ella"
    waste = hass.states.get("sensor.samsas_next_waste_collection")
    assert waste.state == (TODAY + timedelta(days=2)).isoformat() and waste.attributes["title"] == "Sophämtning: Restavfall"
    assert hass.states.get("sensor.samsas_next_mail_day").state == "unknown"

    assert hass.states.get("todo.samsas_shopping_list").state == "1"    # Mjölk open, Smör ticked
    assert hass.states.get("todo.samsas_every_week").state == "1"
    assert hass.states.get("todo.samsas_long_term").state == "1"

    calendar = hass.states.get("calendar.samsas_week")
    assert calendar.attributes["message"] == "🚗 Hämtning Ella – Bo"
    api["state"].assert_awaited_with(TODAY)


async def test_the_lists_write_back(hass: HomeAssistant, api):
    await setup_entry(hass)
    await hass.services.async_call("todo", "add_item", {ATTR_ENTITY_ID: "todo.samsas_shopping_list", "item": "Ägg"}, blocking=True)
    api["add"].assert_awaited_once_with("shopping", "Ägg", due=None)

    await hass.services.async_call("todo", "update_item",
                                   {ATTR_ENTITY_ID: "todo.samsas_every_week", "item": "Dammsuga", "status": "completed"}, blocking=True)
    api["update"].assert_awaited_with(20, text="Dammsuga", done=True, day=TODAY.isoformat())

    await hass.services.async_call("todo", "update_item",
                                   {ATTR_ENTITY_ID: "todo.samsas_long_term", "item": "Måla om hallen", "due_date": "2027-01-15"}, blocking=True)
    api["update"].assert_awaited_with(21, text="Måla om hallen", done=False, due="2027-01-15")

    await hass.services.async_call("todo", "remove_item", {ATTR_ENTITY_ID: "todo.samsas_shopping_list", "item": "Smör"}, blocking=True)
    api["delete"].assert_awaited_once_with(23)


async def test_calendar_asks_by_range_and_lists_the_notices_as_whole_days(hass: HomeAssistant, api):
    await setup_entry(hass)
    start, end = TODAY.isoformat() + "T00:00:00", (TODAY + timedelta(days=7)).isoformat() + "T00:00:00"
    result = await hass.services.async_call("calendar", "get_events",
                                            {ATTR_ENTITY_ID: "calendar.samsas_week", "start_date_time": start, "end_date_time": end},
                                            blocking=True, return_response=True)
    api["events"].assert_awaited_once_with(TODAY, TODAY + timedelta(days=7))
    events = result["calendar.samsas_week"]["events"]
    assert [e["summary"] for e in events] == ["🎒 Lämning Ella – Alva", "🚗 Hämtning Ella – Bo", "⚽ Kalas – ingen än", "Sophämtning: Restavfall"]
    assert events[2]["start"] == (TODAY + timedelta(days=1)).isoformat()      # whole day: a date, not a time


async def test_a_rotated_token_asks_for_a_new_one(hass: HomeAssistant, api):
    entry = await setup_entry(hass)
    api["state"].side_effect = SamsasAuthError()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows and flows[0]["context"]["source"] == "reauth"
    api["state"].side_effect = None
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {"token": "fresh"})
    assert result["type"] == "abort" and result["reason"] == "reauth_successful"
    assert entry.data["token"] == "fresh"
