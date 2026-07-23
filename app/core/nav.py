from fastapi import Request
from organizeme_chrome import NavGroup, build_nav_groups, flat_nav_items, list_apps

from app.models.host_user import HostUser


def sidebar_nav_context(host_user: HostUser | None, request: Request) -> dict[str, object]:
    """Per-request sidebar context: grouped nav, flat nav, and the collapsed-state maps.

    Mirrors doc-library's `app.core.nav.sidebar_nav_context` - reads the user's collapsed-group
    preference from the read-only `HostUser` mapping, since HA Dashboard has no write path to
    persist it (the sidebar's toggle button PATCHes the Host's `/api/v1/users/me` directly,
    routed there by the shared LB regardless of which service rendered the page).

    `host_user` is `None` only in the defensive case `get_host_user()` already handles - falls
    back to nothing collapsed.
    """
    apps = list_apps()
    collapsed = host_user.nav_collapsed_groups if host_user is not None else {}
    nav_groups: list[NavGroup] = build_nav_groups(
        apps, collapsed=collapsed, current_path=request.url.path
    )
    return {
        "nav_groups": nav_groups,
        "flat_nav_items": flat_nav_items(apps),
        "nav_collapsed_json": {group.service_name: group.collapsed for group in nav_groups},
        "nav_stored_collapsed_json": {
            group.service_name: collapsed.get(group.service_name, False) for group in nav_groups
        },
    }
