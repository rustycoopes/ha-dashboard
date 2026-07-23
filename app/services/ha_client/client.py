"""`HAWebSocketClient`: connect -> auth -> 3-command sequencing under one 10s `asyncio.wait_for`
budget. See the TDD's "HA WebSocket client" section and
docs/adr/ha-dashboard-ha-client-module-boundary.md for the design rationale.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.schemas.ha_summary import HASummary, IntegrationError, RepairIssue, UpdateItem
from app.services.ha_client.errors import HAAuthError, HAConnectionError
from app.services.ha_client.transport import HATransport, HATransportFactory, WebSocketsHATransport

_ERROR_CONFIG_ENTRY_STATES = frozenset(
    {"setup_error", "setup_retry", "migration_error", "failed_unload"}
)


class HAWebSocketClient:
    """One entry point, `fetch_dashboard_summary`, used identically by the dashboard tiles
    fragment (Slice 4) and by Settings' Test Connection/Save (Slice 3) - Test Connection
    deliberately reuses this exact full fetch rather than only the auth handshake, per the TDD's
    "deliberate deviation from the PRD's literal wording" (otherwise a non-admin token would pass
    Test Connection and only fail later on the dashboard tiles).
    """

    def __init__(
        self,
        transport_factory: HATransportFactory = WebSocketsHATransport,
        timeout_seconds: float = 10,
    ) -> None:
        self._transport_factory = transport_factory
        self._timeout_seconds = timeout_seconds

    async def fetch_dashboard_summary(self, host: str, token: str) -> HASummary:
        """Raises `HAAuthError` on a rejected token, `HAConnectionError` for everything else
        (timeout, unreachable, malformed response, or a non-admin-token permission failure on one
        of the three commands - see the module-boundary ADR for that bucketing decision). Any
        single command failing collapses the whole fetch, never a partial-success render.
        """
        try:
            return await asyncio.wait_for(self._fetch(host, token), timeout=self._timeout_seconds)
        except TimeoutError as exc:
            raise HAConnectionError("Timed out fetching data from Home Assistant") from exc

    async def _fetch(self, host: str, token: str) -> HASummary:
        # The three _parse_* calls are deliberately inside this same try/except, not just the
        # transport exchange above them - a value that's the right *shape* (e.g. a list) but the
        # wrong *content* (e.g. `{"entity_id": None, ...}`, key present but null) can still raise
        # an unexpected AttributeError/TypeError while parsing. Every route/settings call site
        # trusts the module docstring's promise that only HAAuthError/HAConnectionError or a
        # successful HASummary ever cross this boundary - an exception from parsing is no
        # different from one from the wire exchange itself.
        try:
            async with self._transport_factory(host) as transport:
                await self._authenticate(transport, token)
                states = await self._run_command(transport, 1, "get_states")
                issues = await self._run_command(transport, 2, "repairs/list_issues")
                entries = await self._run_command(transport, 3, "config_entries/get")

            return HASummary(
                fetched_at=datetime.now(UTC),
                pending_updates=_parse_pending_updates(states),
                repair_issues=_parse_repair_issues(issues),
                integration_errors=_parse_integration_errors(entries),
            )
        except (HAAuthError, HAConnectionError):
            raise
        except Exception as exc:
            # Connection refused, DNS failure, a websockets-library exception, a malformed or
            # unexpectedly-shaped payload, etc. - everything not already one of our two taxonomy
            # exceptions collapses to the same generic bucket.
            raise HAConnectionError(str(exc)) from exc

    async def _authenticate(self, transport: HATransport, token: str) -> None:
        greeting = await transport.recv()
        if greeting.get("type") != "auth_required":
            raise HAConnectionError(f"unexpected greeting from Home Assistant: {greeting!r}")

        await transport.send({"type": "auth", "access_token": token})
        response = await transport.recv()
        message_type = response.get("type")
        if message_type == "auth_ok":
            return
        if message_type == "auth_invalid":
            raise HAAuthError(response.get("message", "Home Assistant rejected the token"))
        raise HAConnectionError(f"unexpected auth response from Home Assistant: {response!r}")

    async def _run_command(self, transport: HATransport, command_id: int, command_type: str) -> Any:
        await transport.send({"id": command_id, "type": command_type})
        response = await transport.recv()
        if response.get("id") != command_id or response.get("type") != "result":
            raise HAConnectionError(
                f"unexpected response to {command_type!r} from Home Assistant: {response!r}"
            )
        if not response.get("success"):
            # Bucketed as HAConnectionError, not HAAuthError, even for a non-admin token's
            # permission-denied-shaped failure on config_entries/get - the credential *did*
            # authenticate; see the module-boundary ADR.
            raise HAConnectionError(f"{command_type!r} failed: {response.get('error')!r}")
        return response.get("result")


def get_ha_client() -> HAWebSocketClient:
    """FastAPI dependency yielding the real, `websockets`-backed client.

    Route tests override this via `app.dependency_overrides` with a client built on a scripted
    `FakeHATransport` instead - see tests/test_ha_credential_settings.py.
    """
    return HAWebSocketClient(timeout_seconds=get_settings().ha_fetch_timeout_seconds)


def _parse_pending_updates(states: Any) -> list[UpdateItem]:
    if not isinstance(states, list):
        raise HAConnectionError("get_states did not return a list")
    updates: list[UpdateItem] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        entity_id = state.get("entity_id", "")
        if not entity_id.startswith("update.") or state.get("state") != "on":
            continue
        attributes = state.get("attributes") or {}
        name = attributes.get("friendly_name") or entity_id
        updates.append(UpdateItem(entity_id=entity_id, name=name))
    return updates


def _parse_repair_issues(result: Any) -> list[RepairIssue]:
    if not isinstance(result, dict):
        raise HAConnectionError("repairs/list_issues did not return an object")
    issues = result.get("issues")
    if not isinstance(issues, list):
        raise HAConnectionError("repairs/list_issues result has no 'issues' list")
    parsed: list[RepairIssue] = []
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("ignored"):
            continue
        issue_id = issue.get("issue_id", "")
        translation_key = issue.get("translation_key")
        parsed.append(
            RepairIssue(issue_id=issue_id, name=translation_key)
            if translation_key
            else RepairIssue(issue_id=issue_id)
        )
    return parsed


def _parse_integration_errors(entries: Any) -> list[IntegrationError]:
    if not isinstance(entries, list):
        raise HAConnectionError("config_entries/get did not return a list")
    parsed: list[IntegrationError] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        state = entry.get("state")
        if state not in _ERROR_CONFIG_ENTRY_STATES:
            continue
        parsed.append(
            IntegrationError(
                entry_id=entry.get("entry_id", ""),
                name=entry.get("title") or entry.get("domain") or "Unknown integration",
                state=state,
            )
        )
    return parsed
