# HA Dashboard — PRD

## Problem Statement

Keeping a home Home Assistant instance healthy means periodically checking three different HA
screens by hand — Settings > System > Updates, Settings > System > Repairs, and Settings >
Devices & Services for any integration sitting in an error state. Nothing surfaces those three
signals in one place, so the natural failure mode is not checking at all: pending updates pile up,
a repair issue sits unnoticed, an integration silently stops working.

## Solution

A new, single-purpose hosted app on the OrganizeMe platform, **HA Dashboard**
(`service_name="ha-dashboard"`), following the standard hosted-app pattern (own future repo, own
Cloud Run service, trusts the Host's JWT — see
[`how-to-add-a-hosted-app.md`](../../how-to-add-a-hosted-app.md)). Its one page shows three
read-only status tiles — pending updates, active repair issues, integrations in an error state —
each fetched fresh from Home Assistant's WebSocket API on every page load (no polling, no cache).
Each tile deep-links to the matching HA page for the full picture and any actual remediation; HA
Dashboard itself never takes a write action against HA.

Because the app needs to hold a Home Assistant long-lived access token, it also has a Settings tab
where that token (and the HA host URL) is entered, validated via a live test connection, and
stored encrypted at rest — the only piece of this app that isn't a thin read-only display layer.

## User Stories

1. As the HA Dashboard user, I want to see a count of pending Home Assistant updates, so that I
   know at a glance whether anything needs updating.
2. As the HA Dashboard user, I want to see the names of the pending updates (up to a handful), so
   that I know roughly what's involved without leaving the dashboard.
3. As the HA Dashboard user, I want a "+N more" indicator when there are more pending updates than
   fit in the tile, so that the tile stays glanceable instead of turning into a long list.
4. As the HA Dashboard user, I want to see a count and names of active repair issues, so that I'm
   aware of problems Home Assistant itself has flagged.
5. As the HA Dashboard user, I want ignored repair issues excluded from that count, so that issues
   I've already dismissed in HA don't keep nagging me here.
6. As the HA Dashboard user, I want to see a count and names of integrations currently in an error
   state (setup_error, setup_retry, migration_error, failed_unload), so that I notice a broken
   integration without having to scroll through every configured integration in HA.
7. As the HA Dashboard user, I want each tile to deep-link to the matching HA page, so that I can
   go straight to the place I'd actually act on what the tile is telling me.
8. As the HA Dashboard user, I want tile deep-links to open in a new tab, so that I don't lose my
   place on the dashboard when I follow one.
9. As the HA Dashboard user, I want a tile with a zero count to look visibly different from a tile
   with a non-zero count, so that "everything's fine" is obvious without reading numbers.
10. As the HA Dashboard user, I want to see when the data was last fetched, so that I know how
    fresh what I'm looking at is if I've left the tab open a while.
11. As the HA Dashboard user, I want every visit to the page to re-fetch fresh data from Home
    Assistant, so that I never have to wonder whether I'm looking at stale cached numbers.
12. As the HA Dashboard user, I want a loading indicator while the fetch is in progress, so that I
    know the page is working and not stuck.
13. As the HA Dashboard user, I want the fetch to give up and show an error after a bounded wait
    (~10s), so that a hung connection to Home Assistant doesn't leave me staring at a spinner
    indefinitely.
14. As the HA Dashboard user, I want a clear "Home Assistant rejected the token" message when the
    stored credential is invalid, so that I immediately know the fix is to recheck the token, not
    to troubleshoot my network or HA's uptime.
15. As the HA Dashboard user, I want a generic "couldn't reach Home Assistant" message for every
    other failure (timeout, unreachable, unexpected response), so that I still get useful feedback
    even when the app can't pin down exactly what went wrong.
16. As the HA Dashboard user, I want a distinct "not configured yet" state before I've ever saved
    credentials, so that I'm pointed at Settings instead of shown a connection-failure message for
    a connection that was never attempted.
17. As the HA Dashboard user, I want a Settings tab where I can enter and update the Home Assistant
    host URL and long-lived access token, so that I can set up or rotate the connection without a
    redeploy.
18. As the HA Dashboard user, I want to test the host/token before saving them, so that I catch a
    typo or a bad token immediately rather than discovering it later from the dashboard's error
    tile.
19. As the HA Dashboard user, I want my saved token stored encrypted at rest, so that a database
    read alone can't expose it in plaintext.
20. As the HA Dashboard user, I want the token to never be sent to or held in the browser, so that
    it's never exposed in network traffic or client-side storage.
21. As the HA Dashboard user, I want HA Dashboard to appear in the OrganizeMe sidebar like any
    other hosted app, so that I navigate to it the same way as everything else on the platform.
22. As the HA Dashboard user, I want to reach HA Dashboard only when logged into OrganizeMe, so
    that an unauthenticated visitor is redirected to login rather than seeing my home's status.
23. As the HA Dashboard user, I want HA Dashboard to take no write/control actions against Home
    Assistant, so that a bug in this app can't be the thing that changes something in my house —
    all control stays in the HA app itself.
24. As the HA Dashboard user, I want repair issue names to still show even when Home Assistant
    only provides an internal `translation_key` rather than readable text, so that a missing
    localized title doesn't hide the issue entirely.

## Implementation Decisions

- **New hosted app**, `service_name="ha-dashboard"`, single-purpose (this HA tile row is the whole
  app, not one widget among several) — following the pattern from
  `how-to-add-a-hosted-app.md`, with one deliberate deviation: **no QA Cloud Run environment**.
  There's exactly one real Home Assistant instance to talk to, so a QA deployment would just be
  redundant against the same instance; prod-only is a scoped exception to the platform's standard
  QA+prod pair, to be called out explicitly wherever `/to-design`/`/to-wbs` touch environment
  setup.
- **Access**: standard hosted-app trust model — verifies the Host's JWT cookie, no login of its
  own, no per-app allowlist. Same pattern as `event-creator`/`doc-library`; this app has no
  additional access restriction beyond "logged into the Host."
- **Data source**: Home Assistant's WebSocket API (`wss://<host>/api/websocket`), authenticated
  with the stored long-lived access token, three commands per page load:
  - `get_states`, filtered to `entity_id` starting with `update.` and `state == "on"` → pending
    updates.
  - `repairs/list_issues`, `result.issues[]` excluding any with `ignored: true` → active repair
    issues.
  - `config_entries/get`, filtered to `state` in `{setup_error, setup_retry, migration_error,
    failed_unload}` → integrations in an error state (requires an admin-level token).
  - The fetch is bounded by a ~10s timeout; exceeding it is treated the same as any other
    non-auth failure (generic error state).
- **Dashboard page**: one page, three tiles (updates / repairs / integration errors), each showing
  a count, up to 5 names, and a "+N more" suffix when the count exceeds 5. A zero-count tile gets
  visually distinct "all clear" styling. Repair issue names may fall back to the raw
  `translation_key` string when HA provides no better title — accepted as-is for v1, not
  prettified. The page also shows the fetch timestamp ("as of HH:MM:SS"). No refresh control
  beyond reloading the page; no background polling; no caching of fetched data.
- **Tile states**: not-configured (no credentials saved yet — links to Settings), auth failure
  (credential rejected by HA), generic failure (everything else: timeout, unreachable, malformed
  response), and the normal three-tile success state. These are the only tile states — no further
  breakdown of failure causes.
- **Deep links**: each tile links to its corresponding HA page, opening in a new browser tab.
  Authenticating to HA in that tab (if not already logged in) is expected and out of this app's
  control — HA Dashboard's stored token is a server-side API credential, not a browser session for
  HA itself.
- **Settings tab**: `settings_tabs=[SettingsTab("ha-dashboard", "HA Dashboard")]`-style entry
  managing two fields — HA host URL and the long-lived access token. Saving is gated by a "Test
  Connection" action that performs the same WS auth handshake used by the dashboard fetch before
  the values are persisted, surfacing a bad host/token immediately instead of silently saving it.
  The token is stored encrypted at rest, following `event-creator`'s `CredentialCipher` pattern
  (an `ENCRYPTION_KEY` Secret Manager value, not GCP Secret Manager holding the HA token itself)
  — this is the one piece of state the app owns, and it implies the app needs its own Postgres
  schema and Alembic migration history, which the original plan (token as a Secret-Manager-only
  env var) did not require. This is a real scope addition over that original sketch, confirmed
  deliberately during requirements review.
- **Out-of-scope adjacent capability, noted but not built**: alerting/notifications when a new
  repair issue or pending update appears. HA Dashboard stays a passive, on-demand tile — checking
  it is the only way to find out its current state.

## Testing Decisions

- Good tests here exercise observable behavior at the app's real seams — HTTP responses and
  rendered tile/error/settings states — not internal function calls, and the HA WebSocket client's
  parsing logic specifically, not a live Home Assistant instance.
- **Primary seam for the WS client**: unit tests against a mocked/fake WebSocket server that plays
  back the three expected command/response pairs (auth, `get_states`, `repairs/list_issues`,
  `config_entries/get`) — covering the happy path (correct `HASummary` parsing/filtering) and the
  two tile-facing failure paths (auth rejected, and a generic failure class covering
  timeout/unreachable/malformed response). No live HA token in CI.
- **Page-route seam**: `httpx.AsyncClient` against the real FastAPI app, matching
  `event-creator`/`doc-library` precedent (`test_dashboard_page.py`/`test_doc_library_page.py`
  style) — unauthenticated request redirects to Host login; authenticated request renders each of
  the four tile-row states (not-configured, success, auth failure, generic failure) given a mocked
  WS client dependency; list-truncation ("+N more" at 6+ items) and zero-count "all clear" styling
  are asserted at this seam too.
- **Settings seam**: same HTTP-level pattern — saving valid host/token persists an encrypted row
  and is reflected on the next dashboard fetch; "Test Connection" surfaces a failure without
  persisting anything; the stored token is never present in plaintext in any response body.
- **Manual/live verification** (not automated, done before each deploy): the original plan's
  browser click-through against the real Home Assistant instance — loading state, correct tile
  data, deep-links landing on the right HA page, error tile on a deliberately bad token.
- No boundary/e2e spec is anticipated in `organize-me`'s own suite beyond the existing generic
  Host↔hosted-app auth-trust pattern (`how-to-add-a-hosted-app.md`'s "Test ownership" section) —
  revisit only if a HA-Dashboard-specific auth edge case turns up.

## Out of Scope

- Any control/write action against Home Assistant — this app is read-only, full stop; all
  remediation happens in the HA app itself via the deep links.
- Background polling, caching, or any refresh mechanism beyond a full page reload.
- Proactive alerting or notifications (email, push, etc.) when a metric changes — noted as a
  plausible future enhancement, not part of this PRD.
- Multiple Home Assistant instances, or any per-tile configuration beyond the single host/token
  pair.
- A QA Cloud Run environment (see Implementation Decisions) — prod only.
- Any additional dashboard tiles or widgets beyond the three HA metrics — this app is
  single-purpose by design; a second, unrelated widget would be a separate hosted app.
- Prettifying repair-issue `translation_key` fallback strings into human-readable text.
- Any access restriction beyond the platform's standard "logged into the Host" trust model — no
  per-app allowlist, no admin-only gate.

## Further Notes

- Because the `ha-dashboard` repo doesn't exist yet, this PRD (and the TDD/WBS that follow it)
  live in `organize-me/docs/features/ha-dashboard/`, per the same convention `doc-library` used
  before its own repo was scaffolded — `/new-hosted-app` will carry this directory over once
  design is approved.
- The credential-storage requirement (Settings tab, encrypted at rest, own DB schema) is the
  single biggest divergence from the original plan sketch, which assumed a stateless app with the
  token held only in GCP Secret Manager. Flag this clearly in `/to-design` since it changes the
  app from "no database" to "needs Postgres + Alembic from day one," which in turn affects the
  repo scaffold `/new-hosted-app` produces.
- LLAT must come from an **admin** Home Assistant account — `config_entries/get` requires
  admin-level access to return integration state.
- One-time manual prerequisite: creating the actual long-lived access token in Home Assistant
  (Profile → Security → Long-Lived Access Tokens) is still a human step outside this app; only
  *storing* it moved in-app via Settings.
