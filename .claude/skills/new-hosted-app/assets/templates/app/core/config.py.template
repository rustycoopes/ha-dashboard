from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    database_url: str
    # Same signing key as the Host (Secret Manager secret `jwt-secret-qa`/`jwt-secret-prod`) —
    # this service verifies the Host-issued JWT, it never issues one of its own.
    jwt_secret: str
    # Base URL used to build any absolute links this service needs to construct. Override to
    # http://localhost:8000 in local dev.
    base_url: str = "https://organizeme.russcoopersoftware.com"

    # Add app-specific settings below as they're needed (third-party API keys, feature flags,
    # etc.) — follow the empty-default-with-a-clear-runtime-error pattern used across the other
    # hosted apps for anything that's optional until a specific code path actually uses it.


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
