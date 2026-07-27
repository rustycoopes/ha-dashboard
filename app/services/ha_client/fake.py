"""`HATransport` fake usable both by tests and by `build_ha_transport_factory` under
`settings.mock_integrations` (local-dev-environment Slice 8, organize-me/ha-dashboard#19).

Promoted out of tests/test_ha_client.py, which originally defined this only for its own scripted
`HAWebSocketClient` unit tests - see docs/adr/local-dev-environment-mock-integrations-flag.md
(organize-me) for why it now needs to be importable from application code too.
"""

import copy
from collections.abc import Sequence
from types import TracebackType
from typing import Any

# A believable, self-contained auth-plus-three-command exchange (see
# app.services.ha_client.client.HAWebSocketClient._fetch): one pending update, one repair issue,
# one integration error, so a developer running with mock_integrations=True sees dashboard tiles
# actually render content rather than every section's empty state.
DEFAULT_SCRIPT: Sequence[dict[str, Any]] = (
    {"type": "auth_required", "ha_version": "2026.1.0"},
    {"type": "auth_ok", "ha_version": "2026.1.0"},
    {
        "id": 1,
        "type": "result",
        "success": True,
        "result": [
            {
                "entity_id": "update.home_assistant_core",
                "state": "on",
                "attributes": {"friendly_name": "Home Assistant Core"},
            }
        ],
    },
    {
        "id": 2,
        "type": "result",
        "success": True,
        "result": {
            "issues": [
                {"issue_id": "mock_low_battery", "translation_key": "low_battery", "ignored": False}
            ]
        },
    },
    {
        "id": 3,
        "type": "result",
        "success": True,
        "result": [{"entry_id": "mock_entry", "title": "Mock Integration", "state": "setup_error"}],
    },
)


class FakeHATransport:
    """Plays back a fixed script of `recv()` responses; records every `send()` call.

    Defaults to a fresh deep copy of `DEFAULT_SCRIPT` (a canned successful fetch) when built with
    no arguments - the shape `build_ha_transport_factory` needs, since its `HATransportFactory`
    callable only ever receives a `host` string, never a script. Tests that need to drive a
    specific `HAWebSocketClient` code path (an auth failure, a malformed response, etc.) keep
    passing their own `scripted_recvs` explicitly, same as before this was promoted out of
    tests/test_ha_client.py.
    """

    def __init__(self, scripted_recvs: Sequence[dict[str, Any]] | None = None) -> None:
        recvs = scripted_recvs if scripted_recvs is not None else copy.deepcopy(DEFAULT_SCRIPT)
        self._recvs = iter(recvs)
        self.sent: list[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeHATransport":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    async def recv(self) -> dict[str, Any]:
        return next(self._recvs)
