"""Slice 2 acceptance criteria: /ha-dashboard trusts the Host JWT (signature + expiry only) with
no login/session logic of its own, renders the shared chrome (including dark-mode) for a logged-in
user, and redirects an unauthenticated visitor to the Host's login - proving the cross-repo trust
seam end to end before any real HA integration or feature logic is built.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TokenFactory, create_host_user


async def test_valid_host_jwt_renders_the_empty_state_page(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 200
    assert "HA Dashboard" in response.text
    assert "Home Assistant connection coming soon" in response.text


async def test_no_cookie_redirects_to_host_login(client: AsyncClient) -> None:
    response = await client.get("/ha-dashboard", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_expired_token_redirects_to_host_login(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    token = make_token.expired()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_tampered_signature_redirects_to_host_login(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    token = make_token.tampered()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_garbage_cookie_value_redirects_to_host_login(client: AsyncClient) -> None:
    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": "not-a-jwt"}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_wrong_audience_redirects_to_host_login(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    token = make_token.wrong_audience()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_missing_sub_claim_redirects_to_host_login(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    token = make_token.missing_sub()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_non_uuid_sub_claim_redirects_to_host_login_instead_of_500(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    # Regression test for the fix in app/core/auth.py: a signature/expiry/audience-valid token
    # whose sub isn't a UUID string must redirect like any other untrusted token, not 500.
    token = make_token.non_uuid_sub()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_alg_none_token_redirects_to_host_login(
    client: AsyncClient, make_token: type[TokenFactory]
) -> None:
    # Regression test locking in verify_token()'s explicit algorithms=["HS256"] pin against the
    # classic alg=none JWT bypass.
    token = make_token.alg_none()

    response = await client.get(
        "/ha-dashboard", cookies={"organizeme_auth": token}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_ha_dashboard_page_applies_the_hosts_dark_mode_preference(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session, dark_mode=True)
    token = make_token.valid(sub=str(user_id))

    response = await client.get("/ha-dashboard", cookies={"organizeme_auth": token})

    assert response.status_code == 200
    assert '<html lang="en" class="dark">' in response.text


async def test_ha_dashboard_page_defaults_to_light_mode(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session, dark_mode=False)
    token = make_token.valid(sub=str(user_id))

    response = await client.get("/ha-dashboard", cookies={"organizeme_auth": token})

    assert response.status_code == 200
    assert '<html lang="en" class="">' in response.text


async def test_ha_dashboard_present_in_sidebar_nav(
    client: AsyncClient, db_session: AsyncSession, make_token: type[TokenFactory]
) -> None:
    user_id = await create_host_user(db_session)
    token = make_token.valid(sub=str(user_id))

    response = await client.get("/ha-dashboard", cookies={"organizeme_auth": token})

    assert response.status_code == 200
    assert 'href="/ha-dashboard"' in response.text
