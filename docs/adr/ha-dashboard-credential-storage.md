# HA credential storage: per-user row, shared encryption key

**Status:** Proposed
**Date:** 2026-07-23
**Feature:** [`ha-dashboard`](../features/ha-dashboard/TDD.md)

## Context

The PRD upgraded ha-dashboard from a stateless app (HA token held only in GCP Secret Manager) to
one with an in-app Settings tab that stores the HA host URL and long-lived access token (LLAT)
itself, encrypted at rest. Two sub-decisions fell out of that during `/to-design` that the PRD
didn't pin down:

1. **Shape of the credential row.** Every other Settings-tab-backed table on this platform
   (`event-creator`'s `storage_configs`, `doc-library`'s `user_preferences`) is per-user, one row
   per `host.users.id`. An initial pass at this design considered a global singleton instead
   (reasoning: today there's exactly one physical Home Assistant instance and one LLAT), but that
   was reversed after review — see Decision below.
2. **Encryption key.** `event-creator`'s `CredentialCipher` pattern is keyed by a Secret-Manager
   value (`encryption-key-{qa,prod}`) already shared across every service that needs one. Minting
   `ha-dashboard` its own key was the alternative.

## Decision

- **Per-user credential table** (`ha_dashboard.ha_credential`, `user_id` FK →
  `host.users.id ON DELETE CASCADE`, `UNIQUE(user_id)`), matching the platform's standard shape
  for Settings-tab-backed data (`storage_configs`, `user_preferences`). Each logged-in Host user
  configures and sees only their own HA host URL and token — not a value shared across every
  account. Saving is an atomic per-user `INSERT ... ON CONFLICT (user_id) DO UPDATE`, not
  check-then-insert, so there's no race window if the same user saves from two tabs concurrently.
  Every query (dashboard fetch, Settings read, save, Test Connection) resolves `user_id` from the
  verified JWT (`current_user_id`), never from the request body — the same rule every other hosted
  app's per-user data follows.
- **Host URL stored in plaintext**, token stored encrypted via a ported `CredentialCipher` (own
  copy in `app/core/security.py`, same shape as `event-creator`'s). The host isn't a secret —
  it's the same value the dashboard tiles already link to in a new tab — so encrypting it would
  only add a shared failure mode (a bad/rotated key breaking "is this configured?" rendering, not
  just token use) with no confidentiality benefit.
- **Reuse the existing shared `encryption-key-{qa,prod}` secret** (in practice, `encryption-key-
  prod` only, since ha-dashboard has no QA environment — see the companion ADR). No new Secret
  Manager secret. An HA LLAT is architecturally the same shape of thing `CredentialCipher` already
  protects (an opaque bearer token needing at-rest encryption) — the platform's own bar for a new
  secret is "a genuinely new credential type," which this doesn't meet.

## Alternatives considered

- **Global singleton row** (`id=1`, no `user_id`), on the reasoning that there's only one real HA
  instance today. Rejected: it breaks the platform's otherwise-universal "Settings data is
  per-user" invariant for a reason that's really a *deployment* fact (this operator happens to run
  one HA instance) rather than a *product* constraint — nothing about the app itself should assume
  every Host account wants the same HA connection. A per-user table costs nothing extra when only
  one account actually uses it (it behaves identically to a singleton in that case) but doesn't
  foreclose a second Host user configuring their own HA instance/token later without a schema
  change, and keeps this app consistent with every other hosted app's Settings pattern instead of
  needing its own explained-away exception.
- **New `ha-dashboard`-specific `ENCRYPTION_KEY` secret.** Rejected for now: doesn't raise the
  actual security bar (Secret Manager accessor role, not the number of distinct keys, is the real
  blast-radius boundary — the shared deploy SA already has access to decrypt `event-creator`'s
  credentials too), while adding a second secret to provision, wire into `--set-secrets`, and
  rotate. The one real cost of sharing: `ha-dashboard`'s key can't be rotated in isolation without
  a coordinated re-encrypt across every app using it. No rotation requirement exists today, so this
  isn't worth paying for preemptively — revisit if one ever does.

## Consequences

- Consistent with every other hosted app's Settings-tab data shape — no special-cased schema to
  explain, and `current_user_id` scoping on every route follows the same rule the rest of the
  platform already enforces (an id/row that doesn't belong to the requesting user is invisible to
  them, matching `doc-library`'s 404-not-403 convention).
- Each Host user who logs in and hasn't yet configured their own HA credential sees the
  "not configured" tile state independently — there's no cross-user "someone already set this up"
  shortcut, which is correct given each row is genuinely a different user's own configuration.
- Naturally supports a second Host user configuring a *different* HA instance/token later with zero
  schema change — not a current requirement, but a consequence of matching the platform's default
  shape rather than something specifically designed in.
- The HA LLAT — a credential with physical-world reach into a home network — now sits behind the
  same key as `event-creator`'s lower-stakes OAuth/S3 credentials. No new attacker who could not
  already reach the shared secret gains anything, but it's worth naming explicitly: this is the
  first row behind `ENCRYPTION_KEY` whose compromise has a physical-world consequence, not just a
  cloud-service one.
- **Accepted risk, not a gap: `ha_host_url` is unconstrained user input, and the WS client will
  attempt a connection to whatever it's set to** — no scheme/host allowlist, no blocking of
  private/link-local ranges. This is an SSRF-shaped surface in the abstract (an authenticated Host
  user could point Test Connection/Save at an internal service and use the
  auth-failure/generic-failure/timing distinction as a blind probe), but a denylist on private IP
  ranges would break the feature's actual primary use case — most real Home Assistant instances
  are reached over the home's own local network (`192.168.x.x`, `homeassistant.local`), not solely
  via Nabu Casa's public `https://<id>.ui.nabu.casa`. Narrowing this later is possible (e.g.
  blocking the cloud-metadata IP specifically, `169.254.169.254`, without touching RFC1918/mDNS
  ranges) but isn't done here — flagged explicitly so it reads as a considered trade-off, not an
  oversight, if revisited.
