"""`build_ha_transport_factory` unit tests (local-dev-environment Slice 8) - mirrors
event-creator's `tests/test_storage_factory.py` E2E_TEST_MODE-driven pattern. No live Home
Assistant instance or network access involved.
"""

from app.core.config import Settings
from app.services.ha_client import FakeHATransport, build_ha_transport_factory
from app.services.ha_client.transport import WebSocketsHATransport


def _settings(*, mock_integrations: bool) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",
        jwt_secret="secret",
        mock_integrations=mock_integrations,
    )


def test_mock_integrations_enabled_returns_a_fake_transport_factory() -> None:
    factory = build_ha_transport_factory(_settings(mock_integrations=True))

    transport = factory("https://example.com")

    assert isinstance(transport, FakeHATransport)


def test_mock_integrations_disabled_returns_the_real_transport_factory() -> None:
    factory = build_ha_transport_factory(_settings(mock_integrations=False))

    assert factory is WebSocketsHATransport


def test_mock_integrations_unset_defaults_to_the_real_transport_factory() -> None:
    """Behavior is unchanged from before this slice when the flag isn't touched at all."""
    settings = Settings(database_url="sqlite+aiosqlite://", jwt_secret="secret")

    assert build_ha_transport_factory(settings) is WebSocketsHATransport
