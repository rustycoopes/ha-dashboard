"""Registry-decoupling (organize-me#219): this service's own registry client wiring.

`app/main.py`'s `lifespan` calls `configure_client_registry_source()` again on startup (replacing
the module-level source below with a fresh one) and `start_registry_refresh_task()`/
`stop_registry_refresh_task()` to spawn/cancel the background refresh loop - see
docs/features/registry-decoupling/TDD.md "Background refresh loop (per consumer)" in organize-me.

`SELF_APP_ENTRY` is this service's own copy of the app-registry entry that would otherwise be
authored in organize-me's `app/core/registry.py` - each consumer repo maintains its own copy
(rather than importing the Host's) precisely so it can vouch for its own nav/Settings/API surface
even when the Host is unreachable, per the PRD's "Cold-start fallback" decision.

Registry-decoupling Slice 3 (organize-me#220): `configure_client_registry_source()` is also called
at THIS MODULE's import time (bottom of file), not only inside `lifespan`. `app/main.py`'s own
page router imports transitively import `app.core.templating`, which calls
`organizeme_chrome.templating.register_chrome()` - itself a module-level call to `get_app()` - at
*import* time, before `lifespan` ever runs. Before Slice 3 deleted `organizeme_chrome`'s compiled-in
fallback, an unconfigured `get_app()` silently degraded to that fallback instead of raising, masking
this ordering requirement entirely; now it's a hard crash unless a source is configured before any
router import. `app/main.py` imports this module first, deliberately, for the same reason - see its
own comment.
"""

import asyncio
import contextlib
import logging

import httpx
from organizeme_chrome.registry import AppEntry, AppNavItem, SettingsTab
from organizeme_chrome.registry_client import (
    FetchedRegistrySource,
    build_default_token_provider,
    fetch_registry_once,
)

from app.core.config import Settings

logger = logging.getLogger(__name__)

SELF_APP_ENTRY = AppEntry(
    service_name="ha-dashboard",
    nav=[AppNavItem("/ha-dashboard", "HA Dashboard")],
    settings_tabs=[SettingsTab("ha-dashboard", "HA Dashboard")],
    api_prefixes=["/ha-dashboard/tiles", "/settings/ha-dashboard"],
)


async def _refresh_loop(
    source: FetchedRegistrySource,
    client: httpx.AsyncClient,
    settings: Settings,
) -> None:
    token_provider = build_default_token_provider(settings.registry_host_url)
    fresh_since: str | None = None
    while True:
        try:
            apps = await fetch_registry_once(client, settings.registry_host_url, token_provider)
        except Exception:
            state = f"stale-since-{fresh_since}" if fresh_since else "still-on-cold-start-default"
            logger.warning("registry refresh: fetch failed, serving %s", state, exc_info=True)
        else:
            source.update(apps)
            fresh_since = "now"
            logger.info("registry refresh: freshly-refreshed (%d apps)", len(apps))
        # Fetches immediately on startup, then waits between subsequent attempts - a fresh
        # instance (e.g. after a Cloud Run scale-to-zero cold start) shouldn't serve only its
        # self-only default for a full registry_refresh_interval_seconds before ever trying the
        # Host, per the PRD's "Cold-start fallback" intent (organize-me#218 review feedback).
        await asyncio.sleep(settings.registry_refresh_interval_seconds)


def configure_client_registry_source() -> FetchedRegistrySource:
    from organizeme_chrome.registry import configure_registry_source

    source = FetchedRegistrySource(self_only_default=SELF_APP_ENTRY)
    configure_registry_source(source)
    return source


def start_registry_refresh_task(
    source: FetchedRegistrySource, settings: Settings
) -> tuple[asyncio.Task[None], httpx.AsyncClient]:
    client = httpx.AsyncClient(timeout=settings.registry_fetch_timeout_seconds)
    task = asyncio.create_task(_refresh_loop(source, client, settings))
    return task, client


async def stop_registry_refresh_task(task: asyncio.Task[None], client: httpx.AsyncClient) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await client.aclose()


# Module-import-time side effect - see module docstring. Cheap (no I/O, just object construction)
# and safe to redo again from `lifespan` at real startup.
configure_client_registry_source()
