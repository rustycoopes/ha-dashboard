"""`HAWebSocketClient` unit tests (Slice 3) - a scripted `HATransport` fake drives the client
through the happy path and every failure bucket, per the TDD's "Testability seam" decision. No
live Home Assistant instance/token is involved.
"""

import asyncio
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import pytest

from app.schemas.ha_summary import IntegrationError, RepairIssue, UpdateItem
from app.services.ha_client import HAAuthError, HAConnectionError, HAWebSocketClient


class FakeHATransport:
    """Plays back a fixed script of `recv()` responses; records every `send()` call."""

    def __init__(self, scripted_recvs: Sequence[dict[str, Any]]) -> None:
        self._recvs = iter(scripted_recvs)
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


class HangingHATransport:
    """A transport whose `recv()` never returns - drives the client's own timeout budget."""

    async def __aenter__(self) -> "HangingHATransport":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def send(self, message: dict[str, Any]) -> None:
        return None

    async def recv(self) -> dict[str, Any]:
        await asyncio.sleep(10)
        raise AssertionError("unreachable")


def _client(transport: Any, timeout_seconds: float = 1) -> HAWebSocketClient:
    return HAWebSocketClient(transport_factory=lambda host: transport, timeout_seconds=timeout_seconds)


AUTH_REQUIRED = {"type": "auth_required", "ha_version": "2026.1.0"}
AUTH_OK = {"type": "auth_ok", "ha_version": "2026.1.0"}


def _result(command_id: int, result: Any) -> dict[str, Any]:
    return {"id": command_id, "type": "result", "success": True, "result": result}


async def test_happy_path_parses_and_filters_all_three_commands() -> None:
    transport = FakeHATransport(
        [
            AUTH_REQUIRED,
            AUTH_OK,
            _result(
                1,
                [
                    {
                        "entity_id": "update.core",
                        "state": "on",
                        "attributes": {"friendly_name": "Home Assistant Core"},
                    },
                    {"entity_id": "update.addon", "state": "off", "attributes": {}},
                    {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
                ],
            ),
            _result(
                2,
                {
                    "issues": [
                        {"issue_id": "i1", "translation_key": "low_battery", "ignored": False},
                        {"issue_id": "i2", "translation_key": "dismissed", "ignored": True},
                    ]
                },
            ),
            _result(
                3,
                [
                    {"entry_id": "e1", "title": "Philips Hue", "state": "setup_error"},
                    {"entry_id": "e2", "title": "Spotify", "state": "loaded"},
                ],
            ),
        ]
    )

    summary = await _client(transport).fetch_dashboard_summary("https://example.com", "tok")

    assert summary.pending_updates == [UpdateItem("update.core", "Home Assistant Core")]
    assert summary.repair_issues == [RepairIssue("i1", "low_battery")]
    assert summary.integration_errors == [IntegrationError("e1", "Philips Hue", "setup_error")]
    # The auth exchange plus exactly three sequenced, correctly-numbered commands - never a
    # partial-success render skipping one.
    assert transport.sent == [
        {"type": "auth", "access_token": "tok"},
        {"id": 1, "type": "get_states"},
        {"id": 2, "type": "repairs/list_issues"},
        {"id": 3, "type": "config_entries/get"},
    ]


async def test_repair_issue_with_no_translation_key_falls_back_to_the_schema_default() -> None:
    transport = FakeHATransport(
        [
            AUTH_REQUIRED,
            AUTH_OK,
            _result(1, []),
            _result(2, {"issues": [{"issue_id": "i1", "ignored": False}]}),
            _result(3, []),
        ]
    )

    summary = await _client(transport).fetch_dashboard_summary("https://example.com", "tok")

    assert summary.repair_issues == [RepairIssue("i1")]
    assert summary.repair_issues[0].name == "Unknown issue"


async def test_auth_invalid_raises_ha_auth_error() -> None:
    transport = FakeHATransport(
        [AUTH_REQUIRED, {"type": "auth_invalid", "message": "Invalid access token"}]
    )

    with pytest.raises(HAAuthError, match="Invalid access token"):
        await _client(transport).fetch_dashboard_summary("https://example.com", "bad-token")


async def test_timeout_raises_ha_connection_error() -> None:
    with pytest.raises(HAConnectionError):
        await _client(HangingHATransport(), timeout_seconds=0.05).fetch_dashboard_summary(
            "https://example.com", "tok"
        )


async def test_malformed_auth_response_raises_ha_connection_error() -> None:
    transport = FakeHATransport([AUTH_REQUIRED, {"type": "something_unexpected"}])

    with pytest.raises(HAConnectionError):
        await _client(transport).fetch_dashboard_summary("https://example.com", "tok")


async def test_null_valued_field_during_parsing_raises_ha_connection_error_not_a_raw_exception() -> (
    None
):
    """A `get_states` entry that's the right *shape* (a dict) but the wrong *content* (an
    `entity_id` key present with a `None` value, rather than absent) must still surface as
    `HAConnectionError`, never a raw `AttributeError` escaping the client's documented two-bucket
    boundary - regression test for a parsing step that used to sit outside `_fetch`'s exception
    handling.
    """
    transport = FakeHATransport(
        [
            AUTH_REQUIRED,
            AUTH_OK,
            _result(1, [{"entity_id": None, "state": "on", "attributes": {}}]),
            _result(2, {"issues": []}),
            _result(3, []),
        ]
    )

    with pytest.raises(HAConnectionError):
        await _client(transport).fetch_dashboard_summary("https://example.com", "tok")


async def test_malformed_command_response_raises_ha_connection_error() -> None:
    transport = FakeHATransport([AUTH_REQUIRED, AUTH_OK, {"id": 1, "type": "not_a_result"}])

    with pytest.raises(HAConnectionError):
        await _client(transport).fetch_dashboard_summary("https://example.com", "tok")


async def test_non_admin_token_permission_failure_on_config_entries_buckets_as_connection_error() -> (
    None
):
    """The TDD's resolved Open Question #1: a valid-but-non-admin token authenticates fine
    (auth_ok) and only fails the individual `config_entries/get` command, which HA's own
    `websocket_api.require_admin` decorator surfaces as a normal command-level error result
    (`success: false`), not an auth-handshake rejection - so this buckets as `HAConnectionError`,
    never `HAAuthError`. See docs/adr/ha-dashboard-ha-client-module-boundary.md.
    """
    transport = FakeHATransport(
        [
            AUTH_REQUIRED,
            AUTH_OK,
            _result(1, []),
            _result(2, {"issues": []}),
            {
                "id": 3,
                "type": "result",
                "success": False,
                "error": {"code": "unauthorized", "message": "Unauthorized"},
            },
        ]
    )

    with pytest.raises(HAConnectionError):
        await _client(transport).fetch_dashboard_summary("https://example.com", "non-admin-tok")


async def test_any_single_command_failure_collapses_the_whole_fetch() -> None:
    """Never a partial-success render - `get_states` and `repairs/list_issues` succeeding doesn't
    matter if `config_entries/get` fails; nothing from the first two commands is returned."""
    transport = FakeHATransport(
        [
            AUTH_REQUIRED,
            AUTH_OK,
            _result(1, [{"entity_id": "update.core", "state": "on", "attributes": {}}]),
            _result(2, {"issues": []}),
            {"id": 3, "type": "result", "success": False, "error": {"code": "unknown_error"}},
        ]
    )

    with pytest.raises(HAConnectionError):
        await _client(transport).fetch_dashboard_summary("https://example.com", "tok")
