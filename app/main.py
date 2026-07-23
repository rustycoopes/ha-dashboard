from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Imported first, deliberately - configures organizeme_chrome's registry source (see
# app/core/registry.py's module docstring) before any router module below can call
# organizeme_chrome.get_app()/list_apps() at its own module-import time (app/core/templating.py
# does exactly this, transitively, via app/pages/ha_dashboard.py imported below).
from app.core import registry as _registry  # noqa: F401
from app.core.config import get_settings
from app.core.registry import (
    configure_client_registry_source,
    start_registry_refresh_task,
    stop_registry_refresh_task,
)
from app.pages.ha_dashboard import router as ha_dashboard_router
from app.pages.settings_fragments import router as settings_fragments_router

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Registry-decoupling (organize-me#219): serve this service's own nav/Settings/API surface
    # (SELF_APP_ENTRY) until the first successful background fetch from the Host replaces it -
    # see app/core/registry.py and docs/features/registry-decoupling/TDD.md in organize-me.
    settings = get_settings()
    registry_source = configure_client_registry_source()
    refresh_task, refresh_client = start_registry_refresh_task(registry_source, settings)

    yield

    await stop_registry_refresh_task(refresh_task, refresh_client)
    # Imported here, not at module level, so importing app.main (e.g. for /health tests that
    # never touch the DB) doesn't force DATABASE_URL/Settings to be resolved at import time.
    from app.db.session import get_engine

    await get_engine().dispose()


app = FastAPI(title="HA Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(ha_dashboard_router)
app.include_router(settings_fragments_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
