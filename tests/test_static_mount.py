"""static-asset-routing (ha-dashboard#15): regression coverage for the dual static mount in
app/main.py. The prefixed mount is what fixes the live incident (the shared prod domain falling
through to the Host's CSS); the bare mount must keep working during the one-release transition
window (docs/adr/static-asset-routing-mount-transition.md, in organize-me).
"""

from httpx import AsyncClient
from organizeme_chrome.static_paths import static_mount_path

from app.main import app


def test_both_static_mounts_are_registered() -> None:
    mounted_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert any(path.startswith("/static") for path in mounted_paths)
    assert any(path.startswith(static_mount_path("ha-dashboard")) for path in mounted_paths)


async def test_prefixed_mount_serves_real_content(no_db_client: AsyncClient) -> None:
    path = app.url_path_for("static-prefixed", path="css/app.css")
    assert path == f"{static_mount_path('ha-dashboard')}/css/app.css"

    response = await no_db_client.get(path)

    assert response.status_code == 200
    assert len(response.content) > 0


async def test_bare_mount_still_serves_the_same_content_during_the_transition(
    no_db_client: AsyncClient,
) -> None:
    bare_path = app.url_path_for("static", path="css/app.css")
    prefixed_path = app.url_path_for("static-prefixed", path="css/app.css")

    bare_response = await no_db_client.get(bare_path)
    prefixed_response = await no_db_client.get(prefixed_path)

    assert bare_response.status_code == 200
    assert bare_response.content == prefixed_response.content
