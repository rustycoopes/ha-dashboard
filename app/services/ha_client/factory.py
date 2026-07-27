"""Settings-driven selection of the real vs. fake `HATransportFactory` (local-dev-environment
Slice 8, organize-me/ha-dashboard#19). Mirrors event-creator's
`app.services.storage.factory.build_storage_provider` - see
docs/adr/local-dev-environment-mock-integrations-flag.md (organize-me).
"""

from app.core.config import Settings
from app.services.ha_client.fake import FakeHATransport
from app.services.ha_client.transport import HATransportFactory, WebSocketsHATransport


def build_ha_transport_factory(settings: Settings) -> HATransportFactory:
    if settings.mock_integrations:
        return lambda host: FakeHATransport()
    return WebSocketsHATransport
