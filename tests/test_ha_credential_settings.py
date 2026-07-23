"""HTTP-level tests for the HA connection Settings tab (Slice 3): the Settings fragment,
Test Connection, and Save routes, against the real app + real test Postgres, with
`HAWebSocketClient` dependency-overridden by a fake (`get_ha_client`) - never a real Home
Assistant instance.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ha_credential import HACredential
from tests.conftest import TokenFactory, create_host_user, override_ha_client as _override_ha_client


async def test_settings_fragment_shows_a_reauth_prompt_when_logged_out(
    client: AsyncClient,
) -> None:
    response = await client.get("/settings/ha-dashboard/ha-dashboard")

    assert response.status_code == 200
    assert "Log in" in response.text


async def test_settings_fragment_renders_an_empty_form_when_unconfigured(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)

    response = await client.get("/settings/ha-dashboard/ha-dashboard")

    assert response.status_code == 200
    assert "Not configured yet" in response.text


async def test_settings_fragment_shows_the_saved_host_url_but_never_the_token(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("success")

    save_response = await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://my-home.ui.nabu.casa", "token": "super-secret-llat"},
    )
    assert save_response.status_code == 200
    assert "super-secret-llat" not in save_response.text

    fragment_response = await client.get("/settings/ha-dashboard/ha-dashboard")
    assert "https://my-home.ui.nabu.casa" in fragment_response.text
    assert "super-secret-llat" not in fragment_response.text


async def test_test_connection_success_does_not_persist_anything(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("success")

    response = await client.post(
        "/settings/ha-dashboard/ha-dashboard/test-connection",
        data={"ha_host_url": "https://my-home.ui.nabu.casa", "token": "a-valid-token"},
    )

    assert response.status_code == 200
    assert "Connected successfully" in response.text
    rows = (
        (await db_session.execute(select(HACredential).where(HACredential.user_id == user_id)))
        .scalars()
        .all()
    )
    assert rows == []


async def test_test_connection_auth_failure_shows_the_auth_failure_message(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("auth_failure")

    response = await client.post(
        "/settings/ha-dashboard/ha-dashboard/test-connection",
        data={"ha_host_url": "https://my-home.ui.nabu.casa", "token": "bad-token"},
    )

    assert response.status_code == 200
    assert "rejected the token" in response.text


async def test_test_connection_generic_failure_shows_the_generic_failure_message(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("generic_failure")

    response = await client.post(
        "/settings/ha-dashboard/ha-dashboard/test-connection",
        data={"ha_host_url": "https://unreachable.example.com", "token": "some-token"},
    )

    assert response.status_code == 200
    assert "Could not connect" in response.text


async def test_save_persists_an_encrypted_row_and_sets_last_tested_at(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("success")

    response = await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://my-home.ui.nabu.casa", "token": "super-secret-llat"},
    )

    assert response.status_code == 200
    assert "saved" in response.text.lower()
    assert "super-secret-llat" not in response.text

    row = (
        await db_session.execute(select(HACredential).where(HACredential.user_id == user_id))
    ).scalar_one()
    assert row.ha_host_url == "https://my-home.ui.nabu.casa"
    assert row.encrypted_token != "super-secret-llat"
    assert row.last_tested_at is not None


async def test_saving_again_overwrites_the_same_row_never_a_second(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("success")

    await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://first.example.com", "token": "first-token"},
    )
    first_row = (
        await db_session.execute(select(HACredential).where(HACredential.user_id == user_id))
    ).scalar_one()
    first_id, first_updated_at = first_row.id, first_row.updated_at

    await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://second.example.com", "token": "second-token"},
    )

    rows = (
        (await db_session.execute(select(HACredential).where(HACredential.user_id == user_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id == first_id
    assert rows[0].ha_host_url == "https://second.example.com"
    assert rows[0].updated_at != first_updated_at


async def test_save_failure_persists_nothing_and_shows_the_error(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))
    client.cookies.set("organizeme_auth", token)
    _override_ha_client("auth_failure")

    response = await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://my-home.ui.nabu.casa", "token": "bad-token"},
    )

    assert response.status_code == 200
    assert "rejected the token" in response.text
    rows = (
        (await db_session.execute(select(HACredential).where(HACredential.user_id == user_id)))
        .scalars()
        .all()
    )
    assert rows == []


async def test_a_second_users_settings_fragment_never_shows_the_first_users_host_url(
    client: AsyncClient, make_token: type[TokenFactory], db_session: AsyncSession
) -> None:
    first_user_id = await create_host_user(db_session)
    second_user_id = await create_host_user(db_session)
    first_token = make_token.valid(sub=str(first_user_id))
    second_token = make_token.valid(sub=str(second_user_id))
    _override_ha_client("success")

    client.cookies.set("organizeme_auth", first_token)
    await client.post(
        "/settings/ha-dashboard/ha-dashboard",
        data={"ha_host_url": "https://first-user.example.com", "token": "first-user-token"},
    )

    client.cookies.set("organizeme_auth", second_token)
    response = await client.get("/settings/ha-dashboard/ha-dashboard")

    assert response.status_code == 200
    assert "first-user.example.com" not in response.text
    assert "Not configured yet" in response.text
