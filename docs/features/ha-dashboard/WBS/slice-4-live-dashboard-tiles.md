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

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
