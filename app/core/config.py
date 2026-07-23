from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    database_url: str
    # Same signing key as the Host (Secret Manager secret `jwt-secret-prod` - no QA tier, see
    # docs/adr/ha-dashboard-no-qa-environment.md in organize-me) — this service verifies the
    # Host-issued JWT, it never issues one of its own.
    jwt_secret: str
    # Base URL used to build any absolute links this service needs to construct. Override to
    # http://localhost:8000 in local dev.
    base_url: str = "https://organizeme.russcoopersoftware.com"
    # Registry-decoupling (organize-me#219): the Host's own Cloud Run URL - known in advance (the
    # Host already exists in prod), so this is a plain env var set directly in deploy.yml, no
    # post-deploy capture step needed. Empty default so local dev/CI that hasn't set it yet still
    # starts; the background refresh loop just never succeeds, and this service keeps serving its
    # self-only cold-start default (see docs/adr/registry-decoupling-endpoint-auth.md in
    # organize-me).
    registry_host_url: str = ""
    registry_refresh_interval_seconds: float = 60
    registry_fetch_timeout_seconds: float = 5

    # Add app-specific settings below as they're needed (third-party API keys, feature flags,
    # etc.) — follow the empty-default-with-a-clear-runtime-error pattern used across the other
    # hosted apps for anything that's optional until a specific code path actually uses it.


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
