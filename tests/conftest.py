import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """pytest-homeassistant-custom-component: let hass load custom_components/ from here."""
    yield
