# Slice 4 — Live dashboard tiles

> Part of the `ha-dashboard` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** The actual product — opening `/ha-dashboard` shows a loading indicator, then three
live status tiles (pending updates, active repair issues, integrations in an error state) fetched
fresh from your Home Assistant instance, each deep-linking to the matching HA page, with clear
distinct states for not-yet-configured, success, auth failure, and any other failure.

## What to build

- `GET /ha-dashboard/tiles` — HTMX fragment (`hx-trigger="load"` from the Slice 2 shell), replacing
  the shell's loading placeholder. Resolves the requesting user's `ha_credential` row (Slice 3) and
  renders exactly one of:
  - **Not configured** — no row for this user — a prompt linking to the Settings tab.
  - **Success** — three tiles (updates / repairs / integration errors), each with a count, up to 5
    names, "+N more" beyond that, zero-count tiles styled distinctly ("all clear"), and an
    "as of HH:MM:SS" fetch timestamp.
  - **Auth failure** — `HAAuthError` from the client — "Home Assistant rejected the token."
  - **Generic failure** — `HAConnectionError` (timeout, unreachable, malformed response, or the
    non-admin-permission case from Slice 3) — one generic message.
- Each tile's name/count text links to its corresponding HA page (Settings > System > Updates /
  Repairs / Devices & Services), `target="_blank"`.
- `repairs/list_issues` results excluding `ignored: true`; `config_entries/get` filtered to
  `{setup_error, setup_retry, migration_error, failed_unload}`; a repair issue with no readable
  title falls back to its raw `translation_key` (schema-level default, not a template `or`).
- No refresh control beyond a full page reload; no polling; no caching — every load re-fetches.

## Design notes

Implements the TDD's "Shell-then-fragment rendering" architecture point and the "Presentation
stays out of the client" design decision — this slice owns all of the truncation/all-clear/
timestamp rendering logic; `HASummary` from Slice 3's client arrives untruncated and undecorated.

The shell-then-fragment split is load-bearing, not incidental: `GET /ha-dashboard` (Slice 2)
already returns instantly with a loading placeholder, so this slice's fragment route is the *only*
place the up-to-10s WS fetch happens — confirm the loading placeholder actually renders and holds
until this fragment swaps in, rather than the browser appearing to hang.

## Blocked by

- Slice 3 (needs a real `ha_credential` row and a working `HAWebSocketClient` to fetch against)

## Acceptance criteria

- [ ] A user with no saved credential sees the "not configured" state with a working link to
      Settings.
- [ ] A user with a valid credential sees all three tiles populated with real counts/names from
      the actual Home Assistant instance, matching what those HA screens show directly.
- [ ] A tile with 6+ items shows exactly 5 names plus "+N more"; a zero-count tile is visibly
      styled differently from a non-zero one.
- [ ] Each tile's deep link opens in a new tab and lands on the correct HA page.
- [ ] The "as of" timestamp reflects the actual fetch time, not page-load time or a cached value —
      confirmed by reloading and seeing it change.
- [ ] A deliberately invalid token produces the auth-failure message; a deliberately unreachable
      host (or a fetch exceeding ~10s) produces the generic-failure message.
- [ ] Reloading the page always re-fetches — confirmed by changing something in HA (e.g. dismissing
      a repair issue) and seeing the tile update on the next reload with no manual cache-busting.
- [ ] The page shell renders and the loading indicator is visible before the tiles fragment
      resolves — confirmed by observing the network waterfall, not just the end state.

## Testing

- `tests/test_ha_dashboard_tiles.py` — `httpx.AsyncClient` against the real app + real test
  Postgres, `HAWebSocketClient` dependency overridden with a fake returning each of: no-credential,
  success (varying item counts to exercise truncation and the zero-count/all-clear path), auth
  failure, generic failure. Assert exact rendered content for each state, not just status codes.
- Extends `tests/test_ha_dashboard_page.py` (Slice 2) to confirm the shell route itself still
  returns fast (no WS call) even when the fragment override would be slow — i.e. the shell and
  fragment routes are genuinely decoupled, not just decoupled by convention.
- Manual/live verification (per the TDD's Testing Approach, not automated): full browser
  click-through against the real Home Assistant instance — loading state → tile swap, deep-links
  landing on the right HA page, error tile on a deliberately bad token, and confirming the tile
  data matches what HA's own Updates/Repairs/Devices & Services pages show.

## Delivered

**Issue:** #4 · **Branch:** `feature/slice-4-live-dashboard-tiles` · **Date:** 2026-07-23

Shipped the shell-then-fragment split: the Slice 2 shell (`app/templates/pages/ha_dashboard.html`)
now renders a loading placeholder that HTMX-fetches the new `GET /ha-dashboard/tiles`
(`app/pages/ha_dashboard_tiles.py`) on `hx-trigger="load"`. The fragment resolves the user's
`ha_credential` row, decrypts the token, calls the existing `HAWebSocketClient.fetch_dashboard_summary`
(Slice 3, unchanged), and renders exactly one of the four documented states via a new partial
(`app/templates/partials/ha_dashboard_tiles.html`) - truncation to 5 names + "+N more" and the
zero-count "all clear" styling are decided in `_build_tile`/the template, matching the TDD's
"presentation stays out of the client" decision. All 8 acceptance criteria are covered by
`tests/test_ha_dashboard_tiles.py` and the two new shell-decoupling tests appended to
`tests/test_ha_dashboard_page.py`.

**Fixes from code review (code-review-master + code-quality-guardian), applied before merge:**
- A raw `cryptography.fernet.InvalidToken` on decrypt (e.g. an `ENCRYPTION_KEY` rotation stranding
  an already-stored row) previously propagated to an unhandled 500, leaving the shell's loading
  spinner stuck forever (htmx doesn't swap non-2xx responses by default). Now caught and bucketed
  as `generic_failure`.
- Deep-link hrefs were built by naively concatenating the stored `ha_host_url`, which breaks for a
  scheme-less host (e.g. `homeassistant.local:8123`, a common way to reach a local instance) - the
  browser would resolve it relative to this app's own origin instead of reaching HA. Extracted
  `normalize_host_url`/`PLAINTEXT_SCHEMES` out of `transport.py`'s `_websocket_url` (previously
  private, single-use) into a function shared by both the live WS connection and the tiles
  fragment's `_http_base_url`, so the two always agree on what "the same host" resolves to.
- Deduplicated the `FakeHAWebSocketClient`/`override_ha_client` test double (previously copy-pasted
  between `test_ha_credential_settings.py` and the new `test_ha_dashboard_tiles.py`) into
  `tests/conftest.py`, shared by both.
- Minor: explicit `{% elif state == "success" %}` instead of a catch-all `{% else %}` in the
  partial; fixed a `# type: ignore` workaround in a test helper by typing it correctly instead;
  generalized `settings_reauth_required.html`'s docstring, which is now shared by two fragment
  routes, not one.

**Diverged from the plan:**
- The WBS doesn't specify the exact HA deep-link paths. Used `/config/system/updates`,
  `/config/repairs`, `/config/integrations` (Settings > System > Updates / Repairs, and
  Settings > Devices & Services) as the best-known current Home Assistant frontend routes - **these
  are unverified against a live instance** (no live HA connectivity in this session) and should be
  the first thing checked during the WBS's own "Manual/live verification" step; adjust the three
  path constants in `app/pages/ha_dashboard_tiles.py` if any has moved.
- Could not run the DB-backed half of the test suite locally (no Postgres/Docker available in this
  session's sandbox) - `uv run mypy app tests` passed clean and every DB-independent test passed;
  the full suite, including all of `tests/test_ha_dashboard_tiles.py`, ran for the first time in
  CI on this PR.
- Discovered, but out of scope to fix here: `organize-me`'s Host `/settings` page
  (`app/pages/settings.py`) currently only ever passes `event_creator_app.settings_tabs` into the
  Settings shell template, so ha-dashboard's own registered `settings_tabs` entry (the
  `ha-dashboard` `AppEntry` in `organize-me`'s `app/core/registry.py`) never actually surfaces a
  tab on that page yet. The "not configured" state's link to `/settings` is correct and lands on
  the right page, but the HA Dashboard tab itself won't be visible there until that Host-side gap
  is closed - filed as a separate bug in `organize-me` (not part of this slice/feature).
- Two minor code-review suggestions were left unaddressed (deliberately, both low-priority
  hardening/style, not defects) and filed as a `modelsuggested` follow-up issue instead: no
  `http(s)://` scheme requirement on `ha_host_url` at Settings-save time (Slice 3's schema), and
  the new route's `Literal[...]` state type versus `settings_fragments.py`'s existing plain-`str`
  convention for the same kind of outcome value.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
