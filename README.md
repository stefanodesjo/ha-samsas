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
under **Vi → Home Assistant**, where it can also be rotated; a
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
| `calendar.samsas_week` (Veckan) | The week's events, summaries like the app's calendar feed (`🚗 Hämtning – Bo`, `⛷️ Fjällen – Alva och Bo`, `– ingen än` when nobody has taken it), with end times and multi-day spans, and a shared child's events from the other home. Like the feed, a child's events in the weeks the child is at the other home are left out, and the weeks the child is here show as one entry (`👧 Ella hos oss`; `🏠 Ella och Noah hos oss` for children on the same schedule). Waste and post days, deadlines on Egna listor (`📋 Pass · Packlista`), birthdays, anniversaries, holidays and theme days as whole-day entries. |
| `todo.samsas_shopping_list` (Inköp) | Read-write. `todo.add_item` adds, ticking completes, `todo.remove_item` deletes. Assist's "add … to the shopping list" works on it. A row from the week's menu has the dishes it is for as its description. |
| `todo.samsas_to_do` (Att göra) | The first of Egna listor: the same, with due dates. Installs from before 0.3 keep the old id, `todo.samsas_long_term`. |
| `todo.samsas_<list>` (Packlista, …) | One per list the household makes under Egna listor, named as in the app, with due dates. A new list shows up on its own; a deleted one goes unavailable. |
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

## The house in Samsas

Since 0.4 the house can show up in the app. Under the integration's
**Configure**, pick the entities the family should see (in the order they
should show; the first two without Samsas Plus, up to 24 with it): a temperature, a door, the washing machine, the
electricity price. They appear on the **Huset** card on Hem in Samsas, with
how long each value has been so, written the app's way ("21,5 °C", "Öppen").

A value is sent when it changes, at most once a minute per entity, and the
whole set every 15 minutes; if Samsas hears nothing for 45 minutes the card
says so. Only the current value is sent, never a history. Pick none to
remove the card. Without Plus, Home Assistant shows a notification saying how many of the
picked values the card leaves out; it goes away with Plus or fewer picked.

## Services

`samsas.import_recipe` reads a recipe from a link (or a text) and puts it in
the cookbook, like *Dela till Samsas* in the app. It is part of Samsas Plus.
`member` names the adult whose star it gets (the household's first adult
otherwise). It answers with what was saved:

```yaml
action: samsas.import_recipe
data:
  url: https://www.ica.se/recept/kanelbullar-712345/
  member: Alva
response_variable: saved      # {title, kind: recipe | other, where: Kokboken | Att göra}
```

`samsas.notify` sends the adults a notification through Samsas, in your own
words, so it reaches the whole family even without Home Assistant on their
phones. It is part of Samsas Plus, at most 30 a day. `to` names the adults
(all of them otherwise); `title` defaults to 🏠 Huset.

```yaml
action: samsas.notify
data:
  message: Tvättmaskinen är klar
  title: 🧺 Tvätten
  to: [Alva]
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
entity, the per-child and per-list entities, the writes to the lists, the
calendar, the import service and the reauth after a rotated token.

0.3 needs a Samsas server with Egna listor in `/hass/v1`; against an older
one the new lists, deadlines and *hos oss* weeks are simply absent.
