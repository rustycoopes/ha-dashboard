"""The `HATransport` test seam and its production `websockets`-backed implementation.

`HAWebSocketClient` (client.py) takes an injectable `HATransportFactory` rather than importing
`websockets` directly, so tests drive a scripted `FakeHATransport` fed ordered
(expected-send, canned-recv) pairs matching HA's real message shapes, instead of patching
`websockets.connect` and coupling every test to that library's exact API. See
docs/adr/ha-dashboard-ha-client-module-boundary.md.
"""

import json
from collections.abc import Callable
from types import TracebackType
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import websockets


class HATransport(Protocol):
    """One connection attempt to a specific Home Assistant host.

    Used as an async context manager by `HAWebSocketClient` so a raised exception mid-fetch still
    tears down the socket. `send`/`recv` exchange one JSON message (a dict) at a time - transports
    own their own (de)serialization, `HAWebSocketClient` never touches raw bytes/strings.
    """

    async def __aenter__(self) -> "HATransport": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def send(self, message: dict[str, Any]) -> None: ...

    async def recv(self) -> dict[str, Any]: ...


# A callable that, given the stored `ha_host_url`, builds one (not-yet-connected) transport for a
# single fetch - `HAWebSocketClient` calls this once per `fetch_dashboard_summary`.
HATransportFactory = Callable[[str], HATransport]


_PLAINTEXT_SCHEMES = frozenset({"http", "ws"})


def _websocket_url(host: str) -> str:
    """The `wss://.../api/websocket` (or `ws://` for a plain `http://`/`ws://` host - local
    testing convenience) URL for a stored `ha_host_url` like `https://<id>.ui.nabu.casa`.

    Defaults to `wss` for a bare hostname with no scheme at all, matching every real deployment
    (Nabu Casa remote UI is always `https`) - only an explicit `http://` or `ws://` downgrades to
    `ws`.
    """
    candidate = host.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parts = urlsplit(candidate)
    scheme = "ws" if parts.scheme in _PLAINTEXT_SCHEMES else "wss"
    return urlunsplit((scheme, parts.netloc, "/api/websocket", "", ""))


class WebSocketsHATransport:
    """Production `HATransport`, wrapping `websockets.connect` against a real HA instance."""

    def __init__(self, host: str) -> None:
        self._url = _websocket_url(host)
        self._connection: websockets.ClientConnection | None = None

    async def __aenter__(self) -> "WebSocketsHATransport":
        self._connection = await websockets.connect(self._url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def send(self, message: dict[str, Any]) -> None:
        assert self._connection is not None, "send() called before __aenter__"
        await self._connection.send(json.dumps(message))

    async def recv(self) -> dict[str, Any]:
        assert self._connection is not None, "recv() called before __aenter__"
        raw = await self._connection.recv()
        parsed: Any = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"expected a JSON object from Home Assistant, got {type(parsed)}")
        return parsed
