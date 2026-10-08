# Samsas for Home Assistant

Puts the family's week, tonight's dinner and the lists from
[Samsas](https://samsas.app) into Home Assistant, so a hallway dashboard shows
who collects the kids and "lägg till mjölk på inköpslistan" from a speaker
lands in the app.

## Install

**HACS**: HACS → Integrations → ⋮ → *Custom repositories* → add
`https://github.com/stefanodesjo/ha-samsas` as an *Integration*, then install
*Samsas* and restart Home Assistant.

**By hand**: copy `custom_components/samsas` into `<config>/custom_components/`
and restart.

Then **Settings → Devices & services → Add integration → Samsas**. It asks for
the app's address (`https://samsas.app`) and a token. The token is in the app
under **Vi → Inställningar → Home Assistant**, where it can also be rotated;
a rotated token makes Home Assistant ask for the new one.

What the token reaches is narrow on purpose: the week, the dinner and the
lists. Nothing about how anyone feels, the jar, the cycle log or the money.

## Entities

One device, *Samsas*, with:

| Entity | |
|---|---|
| `calendar.samsas_week` (Veckan) | The week's events, summaries like the app's calendar feed (`🚗 Hämtning – Bo`, `– ingen än` when nobody has taken it), plus waste and post days as whole-day entries. |
| `todo.samsas_shopping_list` (Inköp) | Read-write. `todo.add_item` adds, ticking completes, `todo.remove_item` deletes. Assist's "add … to the shopping list" works on it. |
| `todo.samsas_long_term` (Långsiktigt) | Same, with due dates. |
| `todo.samsas_every_week` (Varje vecka) | Same; completed means done this week. |
| `sensor.samsas_dinner_tonight` (Middag ikväll) | Tonight's dish; the whole week's menu as an attribute. |
| `sensor.samsas_next_pickup` (Nästa hämtning) | The next *hämtning*/*lämning* that has not started: title, with day, time, who and which child as attributes. |
| `sensor.samsas_next_waste_collection`, `sensor.samsas_next_mail_day` | Dates from the household's address notices, when the address is set up in the app. |

Everything refreshes once a minute. Entity ids come from the English names;
the UI shows Swedish when Home Assistant runs in Swedish.

## Development

The server side is `app/homeassistant.py` in the
[samsas](https://github.com/stefanodesjo/samsas) repo: `/hass/v1`, bearer
token per household.

Tests run under Home Assistant's own harness, in a venv of their own
(Python 3.13; the package pins a Home Assistant release, so the install takes
a few minutes):

```bash
python3.13 -m venv .venv && .venv/bin/pip install pytest-homeassistant-custom-component
.venv/bin/python -m pytest -q
```

`tests/test_samsas.py` fakes `/hass/v1` and checks the config flow, each
entity, the writes to the lists and the reauth after a rotated token.
