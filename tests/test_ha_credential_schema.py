"""Pure-schema tests for `_HostAndTokenForm`'s validators (`app/schemas/ha_credential.py`) - no
DB, no app client, just Pydantic construction. Covers the scheme-validation defense in depth added
alongside ha-dashboard#9.
"""

import pytest
from pydantic import ValidationError

from app.schemas.ha_credential import HACredentialWrite


@pytest.mark.parametrize(
    "host",
    [
        "https://my-home.ui.nabu.casa",
        "http://homeassistant.local:8123",
        "homeassistant.local:8123",
        "ws://homeassistant.local:8123",
        "wss://my-home.ui.nabu.casa",
    ],
)
def test_accepts_http_ws_and_schemeless_hosts(host: str) -> None:
    payload = HACredentialWrite(ha_host_url=host, token="a-token")

    assert payload.ha_host_url == host


@pytest.mark.parametrize(
    "host",
    [
        "javascript://alert(1)",
        "ftp://example.com",
        "data://text/html,evil",
        "//attacker.example",
    ],
)
def test_rejects_non_connectable_schemes(host: str) -> None:
    with pytest.raises(ValidationError):
        HACredentialWrite(ha_host_url=host, token="a-token")
