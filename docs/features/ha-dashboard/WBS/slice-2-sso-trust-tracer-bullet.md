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

- [x] Unauthenticated `GET https://organizeme.russcoopersoftware.com/ha-dashboard` redirects to
      the Host's `/login`.
- [x] Authenticated request renders the empty-state page with the shared sidebar/header chrome,
      "HA Dashboard" present in the sidebar nav.
- [x] A user with `dark_mode=true` in their Host Profile sees the page rendered in dark mode (not
      hardcoded light).
- [x] A tampered/garbage `organizeme_auth` cookie value is rejected (treated as unauthenticated),
      not trusted.
- [x] The registry entry's `api_prefixes` (`/ha-dashboard/tiles`, `/settings/ha-dashboard`) are
      present in the regenerated/imported URL map, confirmed by inspecting the imported map — not
      just assumed from the registry source.
- [x] `organizeme-chrome` pin in the new repo matches the registry entry actually live in
      `organize-me`'s `main` at time of merge (no stale-pin gap).

## Testing

HTTP-level: `tests/test_ha_dashboard_page.py` (mirrors `doc-library`'s
`tests/test_doc_library_page.py`) — unauthenticated redirect, authenticated 200 + empty-state
content, tampered-token rejection, `dark_mode` context flows through. No new cross-repo boundary
spec is needed in `organize-me` for this slice specifically — the existing generic
Host↔hosted-app auth-trust coverage already asserts the seam; only add an
`ha-dashboard`-specific boundary spec later if an app-specific auth edge case is found.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered

**Issue:** #2 · **Branch:** `feature/slice-2-sso-trust` · **Date:** 2026-07-23

Shipped the full cross-repo trust seam: `GET /ha-dashboard` in this repo, wired to the shared
`organizeme-chrome` templates/nav, trusting the Host-issued `organizeme_auth` JWT (signature +
expiry only, no network call). `HostUser` is a SELECT-only cross-schema mapping onto `host.users`
reading `dark_mode` + `nav_collapsed_groups`, with a `before_flush` write-guard brought in from
day one (doc-library's own Slice 2 only added this later, as issue #9). Host-side registry entry
(`ha-dashboard` `AppEntry`) added in `organize-me` PR #248 (merged, no `chrome-v*` tag needed —
see below), and `infra/gcp_lb/provision-prod.sh` run to provision `ha-dashboard-prod`'s NEG/
backend service and regenerate/import the prod URL map.

**Diverged from plan — the WBS's own registry-entry instructions were stale.** The WBS/TDD said to
add the `AppEntry` to `packages/chrome/src/organizeme_chrome/registry.py`, matching what
doc-library's Slice 2 actually did. Between then and now, `organize-me` shipped
"registry-decoupling" (#218–#220): the hand-authored `APPS` list moved out of the versioned
`organizeme_chrome` package entirely and into the Host's own `app/core/registry.py`, served over
`GET /internal/app-registry.json` and polled by every consumer's own background refresh loop (this
repo's `app/core/registry.py`, added in this slice, with `SELF_APP_ENTRY` as the cold-start
fallback). Registering `ha-dashboard` therefore needed **zero** `packages/chrome` edit and no new
tag — just an `APPS` list append in `organize-me/app/core/registry.py`. Updated both this WBS file
and the TDD to point at the correct location for future readers.

**Also not anticipated by the WBS: three real gaps found and fixed during implementation.**
1. **CI has no shared `host.users` table.** Unlike doc-library/event-creator, this repo has no QA
   Supabase tier (`docs/adr/ha-dashboard-no-qa-environment.md`) — its CI/smoke-test throwaway
   Postgres never saw `organize-me`'s own migrations, so `0002_grant_host_users_references.py`'s
   `GRANT` and `tests/conftest.py`'s `create_host_user()` had nothing to target. Added
   `scripts/ci/bootstrap_host_users.sql` (column set mirrors `organize-me`'s
   `be144404ee27_create_users_table.py` + `6e2b192a0f9a_add_nav_collapsed_groups...` exactly),
   sourced identically from `ci.yml` and `deploy.yml`'s `smoke-test` job.
2. **No Tailwind CSS build pipeline existed yet.** This is the first slice that actually renders
   the shared chrome — Slice 1 never needed it. Ported `scripts/build_css.py`/
   `verify_css_build.py` and converted the `Dockerfile` to doc-library's multi-stage pattern
   (Tailwind CLI never reaches the runtime image).
3. **`deploy.yml`'s `deploy-prod` job never looked up `REGISTRY_HOST_URL`.** Without it, this
   service's registry refresh loop has no Host URL to poll and stays on its self-only cold-start
   default forever. Added the same "look up the Host's Cloud Run URL" step doc-library's
   `deploy-qa` job uses, targeting `organizeme-prod`.

**Code review (code-review-master + code-quality-guardian):** two real findings applied inline
before merge — `app/models/__init__.py` was empty, so `from app import models` (the mechanism
`migrations/env.py` relies on) never actually registered `HostUser` on `Base.metadata` outside the
running app's own import chain; fixed to mirror doc-library's. `app/core/registry.py`'s cold-start/
refresh-loop behavior had zero test coverage — ported doc-library's
`tests/test_registry_client_wiring.py`. Also deduped the `host.users` bootstrap SQL (was
copy-pasted identically into both workflows) into the single `scripts/ci/bootstrap_host_users.sql`
above, and added a `scripts/build_css.py` mention to the README's "Running locally" section. No
other findings needed a fix or an Intake follow-up.

**Live verification against `https://organizeme.russcoopersoftware.com/ha-dashboard`** (prod-only,
no QA tier, confirmed after the URL map's edge propagation settled):
- Imported URL map (`gcloud compute url-maps describe organizeme-prod-url-map --global`) confirmed
  routing `/ha-dashboard`, `/ha-dashboard/tiles(/*)`, `/settings/ha-dashboard(/*)` to
  `ha-dashboard-backend-prod` — the exact-match-vs-wildcard split the WBS calls out.
- Unauthenticated `GET` → `302` to `/login`.
- Tampered `organizeme_auth` cookie (`garbage.not.a.jwt`) → still `302` to `/login`, not a 500 or a
  trusted session.
- Confirmed no regression on `/dashboard`, `/doc-library`, `/login` after the URL map re-import.

Authenticated-rendering criteria (shared chrome + nav entry + `dark_mode` true/false) were not
re-verified against a live OAuth session — no QA test credentials were available for browser login
(same limitation doc-library's own Slice 2 hit) — but are covered by
`tests/test_ha_dashboard_page.py`'s 13 cases and `tests/test_host_user_model.py`'s 4 write-guard
cases, all green in CI on PR #6 and again after merge in `deploy-prod`'s own Alembic-migration
persistence check.
