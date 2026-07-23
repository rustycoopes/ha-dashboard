# Slice 2 — SSO-trust tracer bullet

> Part of the `ha-dashboard` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** `/ha-dashboard` is reachable through the shared platform domain, appears in the
sidebar, renders the shared chrome (including dark mode) for a logged-in user, and redirects an
unauthenticated visitor to the Host's login — proving the entire cross-repo trust seam end to end
before any real HA integration or feature logic is built.

## What to build

An empty-state `/ha-dashboard` page wired into the full platform seam:

- Pin `organizeme-chrome` in the new repo at the current `chrome-v*` tag; use it to render
  `chrome_base.html`/`chrome_authenticated_base.html` for the page.
- `GET /ha-dashboard` page route: resolves the current user via
  `Depends(current_user_id_optional)` (ported verbatim from the platform's JWT-verify pattern),
  redirects to the Host's `/login` when unauthenticated, otherwise renders an empty-state page
  (no HA data fetch yet — that's Slice 4's job) using the shared chrome.
- Reads and passes `dark_mode` into the template context via a `HostUser`/`get_dark_mode()`
  helper (cross-schema read-only mapping to `host.users`), matching the platform's R7 gotcha
  pattern — do not skip this the way an early `event-creator` page port once did.
- Host-repo PR: add the **full** `ha-dashboard` `AppEntry` to
  `packages/chrome/src/organizeme_chrome/registry.py` —
  `nav=[AppNavItem("/ha-dashboard", "HA Dashboard")]`,
  `settings_tabs=[SettingsTab("ha-dashboard", "HA Dashboard")]`,
  `api_prefixes=["/ha-dashboard/tiles", "/settings/ha-dashboard"]`. The prefixes aren't served by
  any route yet (Slices 3-4 add those), but registering them now avoids a second registry PR
  later — the same move `doc-library`'s Slice 2 made.
- Provision `ha-dashboard-prod`'s Serverless NEG + backend service (`infra/gcp_lb/provision-
  prod.sh`), regenerate the URL map (`infra/gcp_lb/generate_url_map.py prod`) and import it.

## Design notes

Implements the TDD's "Routes and registry entry" section (registry entry + the exact-match-vs-
wildcard LB gotcha it calls out) and the "No login/session code" design decision. See
[`host-integration-guide.md`](../../../host-integration-guide.md) for the general pattern this
follows.

**Sequencing risk (flagged in the TDD, same shape as doc-library's):** the LB provisioning script
will fail if `ha-dashboard-prod` isn't already deployed (Slice 1). Order is strictly: deploy
service → merge registry PR → run `provision-prod.sh` → regenerate/import the URL map.

**LB gotcha, worth re-verifying here specifically** (per the TDD): nav paths get an exact-match-
only rule; only `api_prefixes` entries get the `/*` wildcard. Confirm `/ha-dashboard/tiles` and
`/settings/ha-dashboard` are genuinely covered once the URL map is regenerated, even though
nothing serves them yet — a typo here would silently 404 both later slices' fragment routes
without anyone noticing until Slice 3/4 tries to use them.

## Blocked by

- Slice 1 (needs a deployed `ha-dashboard-prod` Cloud Run service to point the NEG/backend at)

## Acceptance criteria

- [ ] Unauthenticated `GET https://organizeme.russcoopersoftware.com/ha-dashboard` redirects to
      the Host's `/login`.
- [ ] Authenticated request renders the empty-state page with the shared sidebar/header chrome,
      "HA Dashboard" present in the sidebar nav.
- [ ] A user with `dark_mode=true` in their Host Profile sees the page rendered in dark mode (not
      hardcoded light).
- [ ] A tampered/garbage `organizeme_auth` cookie value is rejected (treated as unauthenticated),
      not trusted.
- [ ] The registry entry's `api_prefixes` (`/ha-dashboard/tiles`, `/settings/ha-dashboard`) are
      present in the regenerated/imported URL map, confirmed by inspecting the imported map — not
      just assumed from the registry source.
- [ ] `organizeme-chrome` pin in the new repo matches the registry entry actually live in
      `organize-me`'s `main` at time of merge (no stale-pin gap).

## Testing

HTTP-level: `tests/test_ha_dashboard_page.py` (mirrors `doc-library`'s
`tests/test_doc_library_page.py`) — unauthenticated redirect, authenticated 200 + empty-state
content, tampered-token rejection, `dark_mode` context flows through. No new cross-repo boundary
spec is needed in `organize-me` for this slice specifically — the existing generic
Host↔hosted-app auth-trust coverage already asserts the seam; only add an
`ha-dashboard`-specific boundary spec later if an app-specific auth edge case is found.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
