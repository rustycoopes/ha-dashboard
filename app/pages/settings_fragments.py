"""Settings tab fragment routes for the Host's Settings-shell page (Slice 3).

`GET /settings/ha-dashboard/ha-dashboard` renders the tab's HTML fragment (no
`{% extends "chrome_authenticated_base.html" %}` - just the panel content), consumed by the Host's
Settings shell page via same-origin HTMX fetch, matching event-creator's identical
`app/pages/settings_fragments.py` pattern. `POST .../test-connection` and
`POST /settings/ha-dashboard/ha-dashboard` are also HTML-fragment-returning (this app has no JSON
API surface at all - see the TDD) - both are hit via `hx-post` from the panel's own form.

Unauthenticated requests render `partials/settings_reauth_required.html` with a 200 status (not a
302-to-/login) - see that template's docstring for why a full-page redirect is the wrong shape for
something meant to be swapped into a tab panel.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user_id_optional
from app.core.security import get_credential_cipher
from app.core.templating import templates
from app.db.session import get_db
from app.models.ha_credential import get_ha_credential, upsert_ha_credential
from app.schemas.ha_credential import HACredentialRead, HACredentialWrite, TestConnectionRequest
from app.services.ha_client import HAAuthError, HAConnectionError, HAWebSocketClient, get_ha_client

router = APIRouter(prefix="/settings/ha-dashboard", tags=["pages"])


def _reauth_required(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/settings_reauth_required.html", {})


async def _read_model(db: AsyncSession, user_id: uuid.UUID) -> HACredentialRead:
    credential = await get_ha_credential(db, user_id)
    if credential is None:
        # Unconfigured state: the fragment renders this as an empty form, never an error.
        return HACredentialRead()
    return HACredentialRead(
        configured=True,
        ha_host_url=credential.ha_host_url,
        last_tested_at=credential.last_tested_at,
    )


async def _run_test(ha_client: HAWebSocketClient, host: str, token: str) -> str:
    """Runs the client's full fetch against the given (possibly unsaved) host/token, persisting
    nothing. Test Connection and Save both call this - Test Connection deliberately reuses the
    exact same full fetch the dashboard tiles use, not just the auth handshake, per the TDD's
    "deliberate deviation from the PRD's literal wording" (a non-admin token would otherwise pass
    Test Connection and only fail later on the dashboard tiles).

    Returns one of "success" / "auth_failure" / "generic_failure".
    """
    try:
        await ha_client.fetch_dashboard_summary(host, token)
    except HAAuthError:
        return "auth_failure"
    except HAConnectionError:
        return "generic_failure"
    return "success"


@router.get("/ha-dashboard", response_model=None)
async def ha_dashboard_settings_fragment(
    request: Request,
    user_id: uuid.UUID | None = Depends(current_user_id_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    if user_id is None:
        return _reauth_required(request)
    credential = await _read_model(db, user_id)
    return templates.TemplateResponse(
        request, "partials/settings_ha_dashboard.html", {"credential": credential}
    )


@router.post("/ha-dashboard/test-connection", response_model=None)
async def test_connection_fragment(
    request: Request,
    ha_host_url: str = Form(...),
    token: str = Form(...),
    user_id: uuid.UUID | None = Depends(current_user_id_optional),
    ha_client: HAWebSocketClient = Depends(get_ha_client),
) -> HTMLResponse:
    if user_id is None:
        return _reauth_required(request)

    try:
        payload = TestConnectionRequest(ha_host_url=ha_host_url, token=token)
    except ValidationError:
        return templates.TemplateResponse(
            request, "partials/ha_dashboard_test_connection_result.html", {"outcome": "invalid"}
        )

    outcome = await _run_test(ha_client, payload.ha_host_url, payload.token)
    return templates.TemplateResponse(
        request, "partials/ha_dashboard_test_connection_result.html", {"outcome": outcome}
    )


@router.post("/ha-dashboard", response_model=None)
async def save_ha_credential_fragment(
    request: Request,
    ha_host_url: str = Form(...),
    token: str = Form(...),
    user_id: uuid.UUID | None = Depends(current_user_id_optional),
    db: AsyncSession = Depends(get_db),
    ha_client: HAWebSocketClient = Depends(get_ha_client),
) -> HTMLResponse:
    if user_id is None:
        return _reauth_required(request)

    try:
        payload = HACredentialWrite(ha_host_url=ha_host_url, token=token)
    except ValidationError:
        credential = await _read_model(db, user_id)
        return templates.TemplateResponse(
            request,
            "partials/settings_ha_dashboard.html",
            {"credential": credential, "save_error": "Host and token are required."},
        )

    # Independently re-validates rather than trusting a prior "Test Connection succeeded" result
    # from the client - Test Connection and Save are separate requests, and the token field can be
    # edited in between (TDD's "save-time re-validation" decision).
    outcome = await _run_test(ha_client, payload.ha_host_url, payload.token)
    if outcome != "success":
        credential = await _read_model(db, user_id)
        error_message = (
            "Home Assistant rejected the token."
            if outcome == "auth_failure"
            else "Could not connect to Home Assistant. Check the host URL and try again."
        )
        return templates.TemplateResponse(
            request,
            "partials/settings_ha_dashboard.html",
            {"credential": credential, "save_error": error_message},
        )

    cipher = get_credential_cipher()
    await upsert_ha_credential(
        db,
        user_id,
        ha_host_url=payload.ha_host_url,
        encrypted_token=cipher.encrypt(payload.token),
        tested_at=datetime.now(UTC),
    )
    # get_db doesn't auto-commit, so persist here (savepoint-safe under the test fixture's rolled-
    # back session) - matches event-creator's upsert_storage_config convention.
    await db.commit()

    credential = await _read_model(db, user_id)
    return templates.TemplateResponse(
        request,
        "partials/settings_ha_dashboard.html",
        {"credential": credential, "save_success": True},
    )
