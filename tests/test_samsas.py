"""The component against a faked /hass/v1: setup, the entities, and writes to the lists."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.samsas.api import SamsasAuthError, SamsasError
from custom_components.samsas.const import DOMAIN

TODAY = date.today()


def state_payload() -> dict:
    day = TODAY.isoformat()
    monday = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    return {
        "household": 7, "day": day, "week": monday,
        "members": [{"id": 1, "name": "Alva", "emoji": "🦊"}, {"id": 2, "name": "Bo", "emoji": "🐻"}],
        "kids": [
            {"id": 3, "name": "Ella", "emoji": "👧", "followed": False,
             "custody": {"here": True, "since": monday, "until": (TODAY + timedelta(days=3)).isoformat(), "other_home": "Pappa"},
             "points": {"total": 12, "week": 3}, "chores": {"done": 1, "total": 2, "points": 3}},
            {"id": 4, "name": "Noah", "emoji": "🧒", "followed": True, "custody": None, "points": None, "chores": None},
        ],
        "events": [
            {"id": 10, "day": day, "time": "07:45", "title": "Lämning Ella", "kind": "lamna", "kid_id": 3, "owner_id": 1},
            {"id": 11, "day": day, "time": "23:59", "title": "Hämtning Ella", "kind": "hamta", "kid_id": 3, "owner_id": 2},
            {"id": 12, "day": (TODAY + timedelta(days=1)).isoformat(), "time": None, "title": "Kalas", "kind": "aktivitet", "kid_id": None, "owner_id": None},
            {"id": 13, "day": (TODAY + timedelta(days=4)).isoformat(), "end_day": (TODAY + timedelta(days=8)).isoformat(),
             "time": None, "end_time": None, "title": "Fjällen", "kind": "semester", "emoji": "⛷️", "countdown": True,
             "kid_id": 3, "owner_id": 1, "members": [1, 2], "kids": [3]},
        ],
        "countdowns": [
            {"kind": "anniversary", "title": "Bröllopsdagen", "emoji": "💍", "day": (TODAY + timedelta(days=2)).isoformat(), "days": 2},
            {"kind": "semester", "title": "Fjällen", "emoji": "⛷️", "day": (TODAY + timedelta(days=4)).isoformat(), "days": 4},
        ],
        "dagar": {"day": day, "namnsdag": ["Valfrid", "Manfred"], "helgdag": None, "flaggdag": None, "rod_dag": False, "temadag": "Kanelbullens dag"},
        "swaps": [{"id": 11, "day": day, "time": "23:59", "title": "Hämtning Ella", "kind": "hamta", "from_id": 2, "kid_id": 3}],
        "weekly": {"done": 0, "total": 1},
        "plus": True,
        "dinner": "Tacos",
        "menu": [{"day": monday, "dish": "Tacos"}],
        "lists": {
            "weekly": [{"id": 20, "text": "Dammsuga", "owner_id": None, "kid_id": None, "done": False},
                       {"id": 24, "text": "Duka av", "owner_id": None, "kid_id": 3, "done": True, "points": 3},
                       {"id": 25, "text": "Bädda sängen", "owner_id": None, "kid_id": 3, "done": False, "points": 5}],
            "longterm": [{"id": 21, "text": "Måla om hallen", "owner_id": None, "done": False, "due": "2026-12-01"}],
            "shopping": [{"id": 22, "text": "Mjölk", "owner_id": None, "done": False, "due": None, "dishes": ["Tacos", "Pannkakor"]},
                         {"id": 23, "text": "Smör", "owner_id": None, "done": True, "due": None, "dishes": []}],
        },
        "custom_lists": [{"id": 5, "name": "Packlista", "emoji": "🧳",
                          "items": [{"id": 30, "text": "Pass", "owner_id": None, "done": False, "due": (TODAY + timedelta(days=3)).isoformat()}]}],
        "notices": [{"day": (TODAY + timedelta(days=2)).isoformat(), "kind": "waste", "title": "Sophämtning: Restavfall"}],
    }


@pytest.fixture
def api():
    with patch("custom_components.samsas.api.SamsasApi.state", new_callable=AsyncMock, return_value=state_payload()) as state, \
         patch("custom_components.samsas.api.SamsasApi.events", new_callable=AsyncMock) as events, \
         patch("custom_components.samsas.api.SamsasApi.add_item", new_callable=AsyncMock, return_value={"ok": True, "id": 99}) as add, \
         patch("custom_components.samsas.api.SamsasApi.add_custom_item", new_callable=AsyncMock, return_value={"ok": True, "id": 98}) as add_custom, \
         patch("custom_components.samsas.api.SamsasApi.update_item", new_callable=AsyncMock, return_value={"ok": True}) as update, \
         patch("custom_components.samsas.api.SamsasApi.delete_item", new_callable=AsyncMock, return_value={"ok": True}) as delete, \
         patch("custom_components.samsas.api.SamsasApi.import_recipe", new_callable=AsyncMock,
               return_value={"kind": "recipe", "id": 5, "title": "Kanelbullar", "where": "Kokboken"}) as import_recipe, \
         patch("custom_components.samsas.api.SamsasApi.share_entities", new_callable=AsyncMock, return_value={"shared": 2}) as share, \
         patch("custom_components.samsas.api.SamsasApi.notify", new_callable=AsyncMock, return_value={"to": 2, "left_today": 29}) as notify:
        payload = state_payload()
        events.return_value = {"events": payload["events"], "notices": payload["notices"]}
        yield {"state": state, "events": events, "add": add, "add_custom": add_custom, "update": update, "delete": delete, "import": import_recipe,
               "share": share, "notify": notify}


async def setup_entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Samsas", unique_id="7",
                            data={"url": "https://samsas.test", "token": "secret"}, options=options or {})
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
    assert hass.states.get("todo.samsas_to_do").state == "1"

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
                                   {ATTR_ENTITY_ID: "todo.samsas_to_do", "item": "Måla om hallen", "due_date": "2027-01-15"}, blocking=True)
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
    assert [e["summary"] for e in events] == ["🎒 Lämning Ella – Alva", "🚗 Hämtning Ella – Bo", "⚽ Kalas – ingen än",
                                              "🗑️ Sophämtning: Restavfall", "⛷️ Fjällen – Alva och Bo"]
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


# --- 0.2: the newer features ----------------------------------------------------

async def test_countdowns_name_day_swaps_and_the_weekly_list(hass: HomeAssistant, api):
    await setup_entry(hass)
    soon = hass.states.get("sensor.samsas_next_countdown")
    assert soon.state == "2" and soon.attributes["title"] == "Bröllopsdagen" and len(soon.attributes["upcoming"]) == 2
    name_day = hass.states.get("sensor.samsas_name_day")
    assert name_day.state == "Valfrid, Manfred" and name_day.attributes["theme_day"] == "Kanelbullens dag"
    swaps = hass.states.get("sensor.samsas_swap_requests")
    assert swaps.state == "1" and swaps.attributes["requests"][0]["from"] == "Bo"
    assert hass.states.get("sensor.samsas_left_on_the_weekly_list").state == "1"
    # the adults' weekly list no longer carries the children's chores
    assert hass.states.get("todo.samsas_every_week").state == "1"


async def test_each_child_gets_where_they_are_points_and_chores(hass: HomeAssistant, api):
    await setup_entry(hass)
    custody = hass.states.get("sensor.samsas_ella_is")
    assert custody.state == "here" and custody.attributes["other_home"] == "Pappa"
    points = hass.states.get("sensor.samsas_ella_s_points")
    assert points.state == "12" and points.attributes["this_week"] == 3
    chores = hass.states.get("todo.samsas_ella_s_chores")
    assert chores.state == "1"                                   # Bädda sängen left; Duka av ticked
    # a child shared from another home: no points, no chores, no custody without weeks
    assert hass.states.get("sensor.samsas_noah_s_points") is None
    assert hass.states.get("todo.samsas_noah_s_chores") is None

    await hass.services.async_call("todo", "update_item", {"item": "Bädda sängen", "status": "completed"},
                                   target={ATTR_ENTITY_ID: "todo.samsas_ella_s_chores"}, blocking=True)
    kwargs = api["update"].call_args.kwargs
    assert api["update"].call_args.args == (25,) and kwargs["done"] is True and kwargs["day"]


async def test_a_child_added_in_the_app_shows_up(hass: HomeAssistant, api):
    entry = await setup_entry(hass)
    payload = state_payload()
    payload["kids"].append({"id": 9, "name": "Saga", "emoji": "👶", "followed": False, "custody": None,
                            "points": {"total": 0, "week": 0}, "chores": None})
    api["state"].return_value = payload
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.samsas_saga_s_points").state == "0"


async def test_the_calendar_shows_emoji_people_spans_and_the_days(hass: HomeAssistant, api):
    await setup_entry(hass)
    payload = state_payload()
    api["events"].return_value = {"events": payload["events"], "notices": payload["notices"],
                                  "days": [{"day": (TODAY + timedelta(days=2)).isoformat(), "kind": "anniversary", "title": "💍 Bröllopsdagen · 11 år"}]}
    start, end = TODAY.isoformat(), (TODAY + timedelta(days=14)).isoformat()
    result = await hass.services.async_call("calendar", "get_events", {"start_date_time": f"{start} 00:00:00", "end_date_time": f"{end} 00:00:00"},
                                            target={ATTR_ENTITY_ID: "calendar.samsas_week"}, blocking=True, return_response=True)
    events = {e["summary"]: e for e in result["calendar.samsas_week"]["events"]}
    trip = events["⛷️ Fjällen – Alva och Bo"]
    assert trip["start"] == (TODAY + timedelta(days=4)).isoformat() and trip["end"] == (TODAY + timedelta(days=9)).isoformat()
    assert "💍 Bröllopsdagen · 11 år" in events


async def test_import_recipe_service(hass: HomeAssistant, api):
    await setup_entry(hass)
    result = await hass.services.async_call(DOMAIN, "import_recipe", {"url": "https://example.test/bullar", "member": "bo"},
                                            blocking=True, return_response=True)
    assert result == {"title": "Kanelbullar", "kind": "recipe", "where": "Kokboken"}
    assert api["import"].call_args.args == ("https://example.test/bullar", None, 2)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "import_recipe", {"url": "https://example.test/x", "member": "Dag"}, blocking=True)
    api["import"].side_effect = SamsasError("Att importera recept ingår i Samsas Plus", 402)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "import_recipe", {"text": "Pannkakor"}, blocking=True)


# --- 0.3: Egna listor, deadlines, the weeks a child is here -----------------------

async def test_the_households_own_lists_are_to_do_lists(hass: HomeAssistant, api):
    entry = await setup_entry(hass)
    packing = hass.states.get("todo.samsas_packlista")
    assert packing.state == "1" and packing.attributes["friendly_name"] == "Samsas Packlista"

    await hass.services.async_call("todo", "add_item", {"item": "Laddare", "due_date": "2027-01-10"},
                                   target={ATTR_ENTITY_ID: "todo.samsas_packlista"}, blocking=True)
    api["add_custom"].assert_awaited_once_with(5, "Laddare", due="2027-01-10")
    await hass.services.async_call("todo", "update_item", {"item": "Pass", "status": "completed"},
                                   target={ATTR_ENTITY_ID: "todo.samsas_packlista"}, blocking=True)
    assert api["update"].call_args.args == (30,) and api["update"].call_args.kwargs["done"] is True

    # a list made in the app shows up; one renamed keeps its entity; one deleted goes unavailable
    payload = state_payload()
    payload["custom_lists"][0]["name"] = "Packlista fjällen"
    payload["custom_lists"].append({"id": 6, "name": "Byggvaruhuset", "emoji": "🔨", "items": []})
    api["state"].return_value = payload
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("todo.samsas_packlista").attributes["friendly_name"] == "Samsas Packlista fjällen"
    assert hass.states.get("todo.samsas_byggvaruhuset").state == "0"
    payload["custom_lists"] = payload["custom_lists"][1:]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("todo.samsas_packlista").state == "unavailable"


async def test_a_shopping_row_says_which_dishes_it_is_for(hass: HomeAssistant, api):
    await setup_entry(hass)
    result = await hass.services.async_call("todo", "get_items", {}, target={ATTR_ENTITY_ID: "todo.samsas_shopping_list"},
                                            blocking=True, return_response=True)
    items = {i["summary"]: i for i in result["todo.samsas_shopping_list"]["items"]}
    assert items["Mjölk"]["description"] == "Tacos, Pannkakor" and "description" not in items["Smör"]


async def test_the_calendar_has_deadlines_and_the_weeks_a_child_is_here_not_their_away_events(hass: HomeAssistant, api):
    await setup_entry(hass)
    payload = state_payload()
    payload["events"][2]["away"] = True             # Kalas: only Ella's, in the other home's week
    monday = TODAY - timedelta(days=TODAY.weekday())
    stay = {"start": monday.isoformat(), "end": (monday + timedelta(days=7)).isoformat()}
    api["events"].return_value = {
        "events": payload["events"],
        "notices": payload["notices"] + [{"day": (TODAY + timedelta(days=3)).isoformat(), "kind": "due", "title": "Pass · Packlista"}],
        "stays": [{**stay, "kid_id": 3, "name": "Ella", "emoji": "👧"}, {**stay, "kid_id": 4, "name": "Noah", "emoji": "🧒"},
                  {"start": (monday + timedelta(days=14)).isoformat(), "end": (monday + timedelta(days=21)).isoformat(),
                   "kid_id": 3, "name": "Ella", "emoji": "👧"}],
    }
    result = await hass.services.async_call("calendar", "get_events",
                                            {"start_date_time": f"{TODAY} 00:00:00", "end_date_time": f"{TODAY + timedelta(days=21)} 00:00:00"},
                                            target={ATTR_ENTITY_ID: "calendar.samsas_week"}, blocking=True, return_response=True)
    events = {e["summary"]: e for e in result["calendar.samsas_week"]["events"]}
    assert "⚽ Kalas – ingen än" not in events
    assert "📋 Pass · Packlista" in events
    together = events["🏠 Ella och Noah hos oss"]
    assert together["start"] == monday.isoformat() and together["end"] == (monday + timedelta(days=7)).isoformat()
    assert "👧 Ella hos oss" in events


async def test_nothing_is_shared_until_entities_are_picked(hass: HomeAssistant, api):
    await setup_entry(hass)
    api["share"].assert_not_awaited()


async def test_the_options_pick_what_samsas_shows_and_reload(hass: HomeAssistant, api):
    hass.states.async_set("sensor.vardagsrum", "21.5", {"friendly_name": "Vardagsrummet", "unit_of_measurement": "°C", "device_class": "temperature"})
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form" and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"shared_entities": ["sensor.vardagsrum"]})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options == {"shared_entities": ["sensor.vardagsrum"]}
    entities, = api["share"].await_args.args
    assert api["share"].await_args.kwargs == {"complete": True}
    assert entities == [{"entity_id": "sensor.vardagsrum", "name": "Vardagsrummet", "state": "21.5", "unit": "°C",
                         "device_class": "temperature", "changed_at": hass.states.get("sensor.vardagsrum").last_changed.isoformat()}]


async def test_a_change_goes_at_most_once_a_minute_with_the_newest_value(hass: HomeAssistant, api, freezer):
    hass.states.async_set("binary_sensor.altandorr", "off", {"friendly_name": "Altandörren", "device_class": "door"})
    hass.states.async_set("sensor.saknas_inte", "1")
    await setup_entry(hass, {"shared_entities": ["binary_sensor.altandorr", "sensor.borta"]})
    entities, = api["share"].await_args.args
    assert [e["entity_id"] for e in entities] == ["binary_sensor.altandorr"]       # one that does not exist is left out
    api["share"].reset_mock()
    hass.states.async_set("binary_sensor.altandorr", "on", {"friendly_name": "Altandörren", "device_class": "door"})
    hass.states.async_set("binary_sensor.altandorr", "off", {"friendly_name": "Altandörren", "device_class": "door"})
    await hass.async_block_till_done()
    api["share"].assert_not_awaited()           # sent a moment ago with the full set: wait
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    entities, = api["share"].await_args.args
    assert api["share"].await_count == 1 and entities[0]["state"] == "off" and api["share"].await_args.kwargs == {}


async def test_notify_sends_to_the_adults_named(hass: HomeAssistant, api):
    await setup_entry(hass)
    await hass.services.async_call(DOMAIN, "notify", {"message": "Tvättmaskinen är klar"}, blocking=True)
    api["notify"].assert_awaited_with("Tvättmaskinen är klar", None, None)
    await hass.services.async_call(DOMAIN, "notify", {"message": "Hämta paketet", "title": "📦", "to": ["bo"]}, blocking=True)
    api["notify"].assert_awaited_with("Hämta paketet", "📦", [2])
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "notify", {"message": "x", "to": ["Ingen"]}, blocking=True)
    api["notify"].side_effect = SamsasError("Plus", 402)
    with pytest.raises(ServiceValidationError, match="Samsas Plus"):
        await hass.services.async_call(DOMAIN, "notify", {"message": "x"}, blocking=True)
    api["notify"].side_effect = SamsasError("för många", 429)
    with pytest.raises(ServiceValidationError, match="30"):
        await hass.services.async_call(DOMAIN, "notify", {"message": "x"}, blocking=True)
