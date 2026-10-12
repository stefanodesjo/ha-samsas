![Samsas](https://raw.githubusercontent.com/stefanodesjo/ha-samsas/main/images/header.png)

# Samsas for Home Assistant

Puts the family's week, tonight's dinner, the lists, the children's chores and
what you are counting down to from [Samsas](https://samsas.app) into Home
Assistant, so a hallway dashboard shows who collects the kids, a tablet in a
child's room ticks their chores, and "lägg till mjölk på inköpslistan" from a
speaker lands in the app.

## Install

**HACS**: HACS → Integrations → ⋮ → *Custom repositories* → add
`https://github.com/stefanodesjo/ha-samsas` as an *Integration*, then install
*Samsas* and restart Home Assistant.

**By hand**: copy `custom_components/samsas` into `<config>/custom_components/`
and restart.

Then **Settings → Devices & services → Add integration → Samsas**. It asks for
the app's address (`https://samsas.app`) and a token. The token is in the app
under **Hem → Hemmet → Home Assistant**, where it can also be rotated; a
rotated token makes Home Assistant ask for the new one.

What the token reaches is narrow on purpose: the week, the dinner, the lists,
the children's chores and points, where a child with two homes is, the days
you count down to and the name day. Nothing about how anyone feels, the jar,
the cycle log, the money or the comments. The wishlists stay out too: a
hallway screen would tell a child who bought what.

## Entities

One device, *Samsas*, with:

| Entity | |
|---|---|
| `calendar.samsas_week` (Veckan) | The week's events, summaries like the app's calendar feed (`🚗 Hämtning – Bo`, `⛷️ Fjällen – Alva och Bo`, `– ingen än` when nobody has taken it), with end times and multi-day spans, and a shared child's events from the other home. Waste and post days, birthdays, anniversaries, holidays and theme days as whole-day entries. |
| `todo.samsas_shopping_list` (Inköp) | Read-write. `todo.add_item` adds, ticking completes, `todo.remove_item` deletes. Assist's "add … to the shopping list" works on it. |
| `todo.samsas_long_term` (Långsiktigt) | Same, with due dates. |
| `todo.samsas_every_week` (Varje vecka) | The adults' weekly list; completed means done this week. |
| `todo.samsas_<child>_s_chores` (Ellas sysslor) | One per child: this week's chores. Ticking earns the chore's points, as in the app; adding chores and setting points stay in the app. |
| `sensor.samsas_dinner_tonight` (Middag ikväll) | Tonight's dish; the whole week's menu as an attribute. |
| `sensor.samsas_next_pickup` (Nästa hämtning) | The next *hämtning*/*lämning* that has not started: title, with day, time, who and which child as attributes. |
| `sensor.samsas_next_waste_collection`, `sensor.samsas_next_mail_day` | Dates from the household's address notices, when the address is set up in the app. |
| `sensor.samsas_next_countdown` (Snart) | Days to the nearest anniversary, birthday or event marked *räkna ner*; its title and date, and the next ones, as attributes. |
| `sensor.samsas_name_day` (Namnsdag) | Today's name days; the holiday, flag day, red day and theme day (*kanelbullens dag*) as attributes. |
| `sensor.samsas_swap_requests` (Bytesförfrågningar) | How many *kan du ta?* requests wait for an answer, and which. The answer is a person's, in the app. |
| `sensor.samsas_left_on_the_weekly_list` (Kvar på veckolistan) | What is left on the adults' weekly list. Zero is worth a light show. |
| `sensor.samsas_<child>_is` (Ella är) | For a child with shared custody: `here` or `away` (*Hos oss* / *I andra hemmet*), with the other home and the day of the move. |
| `sensor.samsas_<child>_s_points` (Ellas poäng) | Points since the last reward; this week's points and chores as attributes. |

A child added in the app shows up on its own; a child shared from another home
gets the calendar and *är*, not points or chores, which live in that home.

## Service

`samsas.import_recipe` reads a recipe from a link (or a text) and puts it in
the cookbook, like *Dela till Samsas* in the app. It is part of Samsas Plus.
`member` names the adult whose star it gets (the household's first adult
otherwise). It answers with what was saved:

```yaml
action: samsas.import_recipe
data:
  url: https://www.ica.se/recept/kanelbullar-712345/
  member: Alva
response_variable: saved      # {title, kind: recipe | other, where: Kokboken | Långsiktigt}
```

## Logo

The icon and logo ship with the integration in `custom_components/samsas/brand/`,
which Home Assistant 2026.3 and later shows on its own (after a restart; a
browser that cached the placeholder may need a reload). For older releases the
same files are in `brands/custom_integrations/samsas/`, in the layout of
[home-assistant/brands](https://github.com/home-assistant/brands). They are
drawn by `native/store/ha_brand.py` in the samsas repo, from the same code as
the app icon.

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
entity, the per-child entities, the writes to the lists, the import service
and the reauth after a rotated token.
