"""HTTP-level tests for GET /ha-dashboard/tiles (Slice 4): the HTMX fragment the dashboard shell
loads on `hx-trigger="load"`. Against the real app + real test Postgres, with `HAWebSocketClient`
dependency-overridden by a fake (`get_ha_client`) - never a real Home Assistant instance, matching
tests/test_ha_credential_settings.py's identical pattern for Slice 3.
"""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_credential_cipher
from app.models.ha_credential import upsert_ha_credential
from app.schemas.ha_summary import HASummary, IntegrationError, RepairIssue, UpdateItem
from tests.conftest import TokenFactory, create_host_user, override_ha_client as _override_ha_client


async def _seed_credential(
    db_session: AsyncSession, user_id: uuid.UUID, host: str = "https://my-home.ui.nabu.casa"
) -> None:
    cipher = get_credential_cipher()
    await upsert_ha_credential(
        db_session,
        user_id,
        ha_host_url=host,
        encrypted_token=cipher.encrypt("a-valid-token"),
        tested_at=datetime.now(UTC),
    )
    await db_session.flush()


async def test_no_cookie_shows_reauth_prompt_not_a_redirect(client: AsyncClient) -> None:
    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "Log in" in response.text


async def test_no_saved_credential_shows_the_not_configured_state(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "isn't connected yet" in response.text
    assert 'href="/settings"' in response.text


async def test_auth_failure_shows_the_auth_failure_message(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    await _seed_credential(db_session, user_id)
    _override_ha_client("auth_failure")

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "Home Assistant rejected the token." in response.text


async def test_generic_failure_shows_a_generic_message(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    await _seed_credential(db_session, user_id)
    _override_ha_client("generic_failure")

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "Could not connect to Home Assistant" in response.text


async def test_success_with_zero_counts_shows_all_clear_on_every_tile(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    await _seed_credential(db_session, user_id)
    summary = HASummary(fetched_at=datetime(2024, 1, 1, 10, 30, 15, tzinfo=UTC))
    _override_ha_client("success", summary)

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert response.text.count("All clear") == 3
    assert "10:30:15" in response.text


async def test_success_truncates_names_to_five_and_shows_the_remainder_count(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    host = "https://my-home.ui.nabu.casa"
    await _seed_credential(db_session, user_id, host=host)
    updates = [
        UpdateItem(entity_id=f"update.device_{i}", name=f"Device {i} Update") for i in range(7)
    ]
    summary = HASummary(fetched_at=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC), pending_updates=updates)
    _override_ha_client("success", summary)

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    for i in range(5):
        assert f"Device {i} Update" in response.text
    assert "Device 5 Update" not in response.text
    assert "Device 6 Update" not in response.text
    assert "+2 more" in response.text
    assert f'href="{host}/config/system/updates" target="_blank"' in response.text
    assert f'{host}/config/system/updates">7</a>' in response.text


async def test_success_renders_repair_and_integration_error_deep_links(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    host = "https://my-home.ui.nabu.casa"
    await _seed_credential(db_session, user_id, host=host)
    summary = HASummary(
        fetched_at=datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC),
        repair_issues=[RepairIssue(issue_id="r1", name="Battery low")],
        integration_errors=[
            IntegrationError(entry_id="e1", name="MyIntegration", state="setup_error")
        ],
    )
    _override_ha_client("success", summary)

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "Battery low" in response.text
    assert "MyIntegration" in response.text
    assert f'href="{host}/config/repairs" target="_blank"' in response.text
    assert f'href="{host}/config/integrations" target="_blank"' in response.text


async def test_as_of_timestamp_reflects_the_fetch_time_and_changes_on_reload(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    await _seed_credential(db_session, user_id)

    _override_ha_client("success", HASummary(fetched_at=datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)))
    first = await client.get("/ha-dashboard/tiles")
    assert "08:00:00" in first.text

    _override_ha_client("success", HASummary(fetched_at=datetime(2024, 1, 1, 8, 5, 30, tzinfo=UTC)))
    second = await client.get("/ha-dashboard/tiles")
    assert "08:05:30" in second.text
    assert "08:00:00" not in second.text


async def test_deep_links_default_to_https_for_a_scheme_less_host(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    """A bare hostname (e.g. `homeassistant.local:8123`, common for a local instance) must not
    flow unmodified into an href - a browser would resolve it relative to this app's own origin
    rather than reaching Home Assistant. Mirrors `_websocket_url`'s identical scheme defaulting
    for the live WS connection (transport.py)."""
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    await _seed_credential(db_session, user_id, host="homeassistant.local:8123")
    _override_ha_client("success", HASummary(fetched_at=datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)))

    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert 'href="https://homeassistant.local:8123/config/repairs"' in response.text


async def test_a_second_users_tiles_never_use_the_first_users_credential(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    first_user_id = await create_host_user(db_session)
    second_user_id = await create_host_user(db_session)
    await _seed_credential(db_session, first_user_id, host="https://first-user.example.com")
    fake = _override_ha_client("success", HASummary(fetched_at=datetime.now(UTC)))

    client.cookies.set("organizeme_auth", make_token.valid(sub=str(second_user_id)))
    response = await client.get("/ha-dashboard/tiles")

    assert response.status_code == 200
    assert "isn't connected yet" in response.text
    assert fake.calls == []
