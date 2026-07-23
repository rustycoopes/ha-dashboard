"""The two-bucket failure taxonomy `HAWebSocketClient` raises out of the client boundary.

Nothing HA-protocol-specific crosses this boundary - route/settings code only ever sees one of
these two exceptions or a successful `HASummary`. See
docs/adr/ha-dashboard-ha-client-module-boundary.md and the TDD's "HA WebSocket client" section for
the full rationale, including why a command-level permission failure (a valid but non-admin token
failing `config_entries/get` after a successful auth) buckets as `HAConnectionError`, not
`HAAuthError` - the credential *did* authenticate; it just isn't privileged enough for one of the
three commands.
"""


class HAAuthError(Exception):
    """Home Assistant rejected the token at the auth handshake itself (`auth_invalid`)."""


class HAConnectionError(Exception):
    """Every other failure: timeout, connection refused, malformed response, or a command-level
    permission failure after a successful auth."""
