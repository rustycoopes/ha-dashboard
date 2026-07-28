"""Request/response shapes for the HA connection Settings tab (Slice 3).

`HACredentialRead` is masked - it never carries the token, even encrypted, matching the
acceptance criteria that the token must never appear in any response body.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.ha_client.transport import PLAINTEXT_SCHEMES, normalize_host_url

# The only schemes `normalize_host_url`/the WS client know how to connect with - `PLAINTEXT_SCHEMES`
# is `_websocket_url`'s existing "explicit http://ws:// downgrades to plaintext" allow-list; the
# secure counterparts (`https`/`wss`) are always accepted. Derived rather than a second hand-
# maintained literal set, so the two can't silently drift apart.
_ALLOWED_HOST_SCHEMES = PLAINTEXT_SCHEMES | {"https", "wss"}


class HACredentialRead(BaseModel):
    """The Settings fragment's render model. All-default (``configured=False``) is the
    unconfigured state the fragment renders as an empty form, not an error.
    """

    model_config = ConfigDict(from_attributes=True)

    configured: bool = False
    ha_host_url: str | None = None
    last_tested_at: datetime | None = None


class _HostAndTokenForm(BaseModel):
    """Shared validation for the two form posts that submit a host/token pair - Test Connection
    and Save both independently re-validate rather than trusting each other's result, per the
    TDD's "save-time re-validation" decision.
    """

    ha_host_url: str
    token: str

    @field_validator("ha_host_url", "token")
    @classmethod
    def _strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("ha_host_url")
    @classmethod
    def _require_connectable_scheme(cls, value: str) -> str:
        """Defense in depth, not closing an XSS hole - `_http_base_url`/`_websocket_url` already
        force the *emitted* scheme to http(s)/ws(s) regardless of what's stored, so a submitted
        scheme never reaches a live `href` unchanged. Without this validator, garbage input (e.g.
        `//attacker.example`, which resolves to an empty netloc) would only fail later, either
        silently as a broken deep link (`https:///config/...`) or as an opaque WS-connect failure
        - this surfaces it as a clear validation error at submission time instead. Schemeless
        input (a bare hostname like `homeassistant.local:8123`, the common way to reach a local HA
        instance) is fine - `normalize_host_url` defaults it to `https`, the same scheme-
        defaulting the WS client and tiles fragment already apply.
        """
        parts = normalize_host_url(value)
        if not parts.netloc or parts.scheme not in _ALLOWED_HOST_SCHEMES:
            raise ValueError("host must be an http(s) or ws(s) URL, or a bare hostname")
        return value


class TestConnectionRequest(_HostAndTokenForm):
    """``POST .../test-connection``'s submitted (unsaved) host/token pair."""


class HACredentialWrite(_HostAndTokenForm):
    """``POST /settings/ha-dashboard/ha-dashboard``'s submitted host/token pair to persist."""
