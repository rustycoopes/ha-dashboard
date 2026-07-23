"""Request/response shapes for the HA connection Settings tab (Slice 3).

`HACredentialRead` is masked - it never carries the token, even encrypted, matching the
acceptance criteria that the token must never appear in any response body.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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


class TestConnectionRequest(_HostAndTokenForm):
    """``POST .../test-connection``'s submitted (unsaved) host/token pair."""


class HACredentialWrite(_HostAndTokenForm):
    """``POST /settings/ha-dashboard/ha-dashboard``'s submitted host/token pair to persist."""
