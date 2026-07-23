"""`GET /ha-dashboard/tiles` (Slice 4): the HTMX fragment the Slice 2 shell's loading placeholder
fetches on `hx-trigger="load"`. This is the *only* place the up-to-10s `HAWebSocketClient` fetch
happens - see docs/features/ha-dashboard/WBS/slice-4-live-dashboard-tiles.md's "shell-then-
fragment" design note.

Renders exactly one of four states: not-configured (no `ha_credential` row), success (three
tiles), auth failure, or generic failure. All truncation/all-clear/timestamp presentation logic
lives here and in the partial template - `HASummary` itself arrives untruncated and undecorated
(see schemas/ha_summary.py's module docstring).

Unauthenticated requests render `partials/settings_reauth_required.html` with a 200 status, not a
302 - same reasoning as settings_fragments.py: this is fragment content swapped into a shell page
via htmx, and a redirect response would have htmx swap the Host's full login-page HTML into the
tiles placeholder instead of navigating there.
"""

import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlunsplit

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user_id_optional
from app.core.security import get_credential_cipher
from app.core.templating import templates
from app.db.session import get_db
from app.models.ha_credential import get_ha_credential
from app.schemas.ha_summary import HASummary, IntegrationError, RepairIssue, UpdateItem
from app.services.ha_client import HAAuthError, HAConnectionError, HAWebSocketClient, get_ha_client
from app.services.ha_client.transport import PLAINTEXT_SCHEMES, normalize_host_url

router = APIRouter(tags=["pages"])

# A tile shows at most this many names before collapsing the rest into "+N more" - see the WBS
# slice's acceptance criteria.
_MAX_TILE_NAMES = 5

# Deep-link targets on the user's own HA instance (Settings > System > Updates / Repairs, and
# Settings > Devices & Services) - relative paths, joined to the credential's `ha_host_url`.
_UPDATES_PATH = "/config/system/updates"
_REPAIRS_PATH = "/config/repairs"
_INTEGRATIONS_PATH = "/config/integrations"


def _http_base_url(host: str) -> str:
    """An absolute `http(s)://host` base to prefix a deep-link path with.

    Reuses `normalize_host_url`'s scheme-defaulting (shared with `_websocket_url`, the live WS
    connection) - a bare hostname like `homeassistant.local:8123`, a common way to reach a local
    HA instance, would otherwise flow unmodified into `href="homeassistant.local:8123/..."`, which
    a browser resolves relative to *this app's own* origin rather than reaching HA at all.
    """
    parts = normalize_host_url(host)
    scheme = "http" if parts.scheme in PLAINTEXT_SCHEMES else "https"
    return urlunsplit((scheme, parts.netloc, "", "", ""))


@dataclass(frozen=True)
class TileView:
    """Presentation-ready view of one tile - built here from a raw `HASummary` list, never passed
    to the template as-is (per the TDD's "presentation stays out of the client" decision)."""

    title: str
    count: int
    names: list[str]
    more_count: int
    deep_link: str


def _build_tile(
    title: str, items: list[UpdateItem] | list[RepairIssue] | list[IntegrationError], deep_link: str
) -> TileView:
    return TileView(
        title=title,
        count=len(items),
        names=[item.name for item in items[:_MAX_TILE_NAMES]],
        more_count=max(len(items) - _MAX_TILE_NAMES, 0),
        deep_link=deep_link,
    )


def _build_tiles(summary: HASummary, host: str) -> list[TileView]:
    base = _http_base_url(host)
    return [
        _build_tile("Pending Updates", summary.pending_updates, base + _UPDATES_PATH),
        _build_tile("Repair Issues", summary.repair_issues, base + _REPAIRS_PATH),
        _build_tile("Integration Errors", summary.integration_errors, base + _INTEGRATIONS_PATH),
    ]


State = Literal["not_configured", "success", "auth_failure", "generic_failure"]


def _render(request: Request, state: State, **extra: object) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "partials/ha_dashboard_tiles.html", {"state": state, **extra}
    )


@router.get("/ha-dashboard/tiles", response_model=None)
async def ha_dashboard_tiles_fragment(
    request: Request,
    user_id: uuid.UUID | None = Depends(current_user_id_optional),
    db: AsyncSession = Depends(get_db),
    ha_client: HAWebSocketClient = Depends(get_ha_client),
) -> HTMLResponse:
    if user_id is None:
        return templates.TemplateResponse(request, "partials/settings_reauth_required.html", {})

    credential = await get_ha_credential(db, user_id)
    if credential is None:
        return _render(request, "not_configured")

    cipher = get_credential_cipher()
    try:
        token = cipher.decrypt(credential.encrypted_token)
    except InvalidToken:
        # ENCRYPTION_KEY rotated out from under an already-stored row, or row corruption - bucketed
        # as generic_failure since it's not something re-entering the same token in Settings would
        # fix (the token itself may be fine; the stored ciphertext no longer decrypts).
        return _render(request, "generic_failure")

    try:
        summary = await ha_client.fetch_dashboard_summary(credential.ha_host_url, token)
    except HAAuthError:
        return _render(request, "auth_failure")
    except HAConnectionError:
        return _render(request, "generic_failure")

    tiles = _build_tiles(summary, credential.ha_host_url)
    return _render(request, "success", tiles=tiles, fetched_at=summary.fetched_at)
