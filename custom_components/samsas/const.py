"""Constants for the Samsas integration."""

from datetime import timedelta
import logging

DOMAIN = "samsas"
LOGGER = logging.getLogger(__package__)

CONF_URL = "url"
CONF_TOKEN = "token"
DEFAULT_URL = "https://samsas.app"

# The app's own clients poll every 30 s while open; a house can wait a minute.
UPDATE_INTERVAL = timedelta(seconds=60)

# Same glyphs as the app's calendar feed, so a dashboard reads like the subscription does.
KIND_EMOJI = {"lamna": "🎒", "hamta": "🚗", "aktivitet": "⚽", "egentid": "🌿", "ovrigt": "📌", "semester": "🏖️"}
PICKUP_KINDS = ("hamta", "lamna")
# An event with a start and no end: half an hour is about a pickup.
TIMED_MINUTES = 30

SERVICE_IMPORT_RECIPE = "import_recipe"
ATTR_URL = "url"
ATTR_TEXT = "text"
ATTR_MEMBER = "member"
ATTR_CONFIG_ENTRY = "config_entry_id"
