"""Legacy domain tests opt into local mode; authentication tests explicitly enable it."""

import pytest

from interaction_studio_api.config import get_settings


@pytest.fixture(autouse=True)
def isolated_auth_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
