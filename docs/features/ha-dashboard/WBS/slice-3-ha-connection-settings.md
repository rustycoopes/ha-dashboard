# Slice 3 — HA connection settings

> Part of the `ha-dashboard` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A logged-in user can open the HA Dashboard Settings tab, enter their Home Assistant
host URL and long-lived access token, verify it actually works via Test Connection before saving,
and have it stored — encrypted, scoped to their own account — ready for Slice 4's dashboard tiles
to use.

## What to build

The full HA connection management path, end to end:

- `ha_dashboard.ha_credential` table + Alembic migration: per-user (`user_id` FK →
  `host.users.id`, `ON DELETE CASCADE`, `UNIQUE`), `ha_host_url` (plaintext), `encrypted_token`,
  `last_tested_at`, `updated_at`. See the
  [credential storage ADR](../../../adr/ha-dashboard-credential-storage.md) for why per-user
  (not a global singleton) and why the host URL isn't encrypted.
- `CredentialCipher` — a ported copy (own module, not a shared package) of `event-creator`'s
  Fernet-based cipher, keyed by the (already-granted, per Slice 1) shared `ENCRYPTION_KEY`.
- The `HAWebSocketClient` itself (`app/services/ha_client/`): an injectable `HATransport` protocol
  seam, the production `websockets`-backed implementation, connect→auth→3-command sequencing
  under one `asyncio.wait_for(10s)` budget, and the `HAAuthError`/`HAConnectionError` failure
  taxonomy — including the decision that a command-level permission failure (e.g. a non-admin
  token failing `config_entries/get` after a successful auth) buckets as `HAConnectionError`, not
  `HAAuthError`. **Before finalizing that bucketing, spike against a real non-admin LLAT** (TDD
  Open Question #1) to confirm HA's actual WS error shape matches this assumption — if it
  auth-rejects at the handshake level instead, adjust the taxonomy accordingly.
- `GET /settings/ha-dashboard/ha-dashboard` — Settings tab fragment: shows the current host URL
  (or an empty form if unconfigured) and never returns the token, even encrypted.
- `POST /settings/ha-dashboard/ha-dashboard/test-connection` — runs the client's full fetch
  against the *submitted* (unsaved) host/token, returns an inline success/fail fragment, persists
  nothing.
- `POST /settings/ha-dashboard/ha-dashboard` — independently re-validates (never trusts a prior
  Test Connection result from the client) and atomically upserts
  (`INSERT ... ON CONFLICT (user_id) DO UPDATE`) the requesting user's row, setting
  `last_tested_at` on success.

## Design notes

Implements the TDD's "Credential schema" and "HA WebSocket client" sections in full, and the
[module boundary ADR](../../../adr/ha-dashboard-ha-client-module-boundary.md)'s reasoning for why
this app gets a dedicated `services/ha_client/` package despite `doc-library`'s "no `services/`"
precedent.

**Deliberate deviation from the PRD's literal wording, already resolved in the TDD:** Test
Connection runs the *full* 3-command fetch, not just the auth handshake — otherwise a non-admin
token would pass Test Connection and only fail later on the dashboard tiles, defeating the point
of testing first. See the TDD's "HA WebSocket client" section for the full rationale.

## Blocked by

- Slice 2 (needs the registry's `settings_tabs` entry live and `/settings/ha-dashboard` routed
  through the LB, plus the reachable authenticated app shell to host the fragment)

## Acceptance criteria

- [ ] A logged-in user with no saved credential sees an empty Settings form, not an error.
- [ ] Test Connection against a valid admin-level host/token returns a success fragment and
      persists nothing (confirmed by checking no row exists yet).
- [ ] Test Connection against an invalid token returns the auth-failure message; against an
      unreachable host, the generic-failure message.
- [ ] Test Connection against a valid but **non-admin** token fails with a message consistent with
      the TDD's chosen bucketing (spiked and confirmed per the Open Question above, adjusted if
      reality differs from the assumption).
- [ ] Saving valid host/token persists an encrypted row; the token is never present in plaintext
      in any response body (fragment HTML, logs, or otherwise).
- [ ] Saving again as the same user overwrites their existing row (confirmed via `updated_at`
      changing), never creating a second row.
- [ ] A second Host user's Settings page shows their own (independently empty or configured)
      state — never the first user's host URL or any indication a token exists for someone else.
- [ ] Deleting a Host user cascades to delete their `ha_credential` row (`ON DELETE CASCADE`
      verified at the DB level, not just assumed from the FK definition).

## Testing

- `tests/test_ha_client.py` — `HATransport` fakes drive: happy path (correct `HASummary`
  parsing/filtering), `auth_invalid` → `HAAuthError`, timeout → `HAConnectionError`, malformed
  response → `HAConnectionError`, and the non-admin-token command failure → `HAConnectionError`
  (once the spike above confirms this is the right bucket). No live HA token in CI.
- `tests/test_ha_credential_settings.py` — `httpx.AsyncClient` against the real app + real test
  Postgres, `HAWebSocketClient` dependency overridden with a fake: Settings fragment renders
  correctly configured/unconfigured; Test Connection surfaces success/auth-failure/generic-failure
  without persisting; Save persists and re-validates independently; cross-user isolation (never
  another user's row, matching `doc-library`'s "never another user's row, even by guessing an id"
  convention — 404, not 403).
- `tests/test_ha_credential_model.py` — concurrent same-user upsert resolves to one row
  (last-write-wins, no unique-constraint violation); `ON DELETE CASCADE` against `host.users`,
  matching `doc-library`'s `test_doc_link_model.py` pattern.
- Manual: a real Test Connection against the actual Home Assistant instance, using both an
  admin-level and (if feasible to create one) a deliberately non-admin LLAT, to ground-truth the
  taxonomy spike before this slice is considered done.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
