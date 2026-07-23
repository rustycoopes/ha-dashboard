# How to Add a Hosted App

This is the playbook for standing up a **new** hosted app in the OrganizeMe platform — the
process `event-creator` (R6-R13) established, now written up as a repeatable pattern per the
Platform Restructure PRD's "adding a future app's nav entry + settings tab is a single Host
config change + redeploy" success metric.

It complements [`host-integration-guide.md`](host-integration-guide.md) (the slice-by-slice
"what infra/routing/secrets did each Platform Restructure slice actually require" log) — this
doc is the condensed, forward-looking "start here" version for app #3 and beyond. Every example
below is the real `event-creator` entry/config, not a hypothetical.

Before starting, skim `host-integration-guide.md`'s ["Manual steps a human must do outside the
repo"](host-integration-guide.md#manual-steps-a-human-must-do-outside-the-repo) checklist — several
of the steps below (provisioning infra, registering OAuth redirect URIs, creating secrets) are
things an operator does by hand via `gcloud`/Console, not something this repeatable pattern
automates.

## 0. The one-sentence version

A hosted app is its own repo, its own Cloud Run service(s), and its own DB schema; it never
handles login, sessions, or passwords; it trusts a Host-issued JWT cookie; and it plugs into the
Host's sidebar/Settings/Load-Balancer routing by adding one entry to the Host's own app-registry
data (`app/core/registry.py` in this repo) and wiring the standard `configure_registry_source()`
background-refresh client into its own `lifespan` — **not** by bumping a package pin in every
existing consumer repo (registry-decoupling Slice 3, organize-me#220 retired that older
mechanism).

## 1. The Host app-registry entry

`app/core/registry.py` (this repo only) is the single source of truth for a hosted app's nav
items, Settings tabs, and API path prefixes. Rendering (the shared chrome package, in every
consumer) and the Load Balancer's routing (step 2 below) are both driven from this one list —
never hand-maintain either separately. The Host serves it at
`GET /internal/app-registry.json`; every other consumer's own background refresh loop
(`configure_client_registry_source()` + `start_registry_refresh_task()`, step 3) polls that
endpoint and caches the result — a hosted app never edits `organizeme_chrome`'s package code to
add its own nav entry, only this one Host-repo file.

The real `event-creator` entry, as of registry-decoupling Slice 1:

```python
AppEntry(
    service_name="event-creator",
    nav=[
        AppNavItem("/dashboard", "Dashboard"),
        AppNavItem("/upload", "Upload"),
        AppNavItem("/processing", "Processing"),
        AppNavItem("/logs", "Logs"),
        AppNavItem("/prompt", "Prompt"),
    ],
    settings_tabs=[
        SettingsTab("storage", "Storage"),
        SettingsTab("notifications", "Notifications"),
        SettingsTab("preferences", "Preferences"),
    ],
    api_prefixes=[
        "/api/v1/storage-config",
        "/api/v1/user-settings",
        "/settings/event-creator",
        "/api/v1/events",
        "/api/v1/llm-prompt",
        "/api/v1/upload",
        "/api/v1/import-pending-files",
        "/api/v1/processing-runs",
        "/processing-runs",
        "/api/html/processing-runs",
    ],
),
```

What each field does:

- **`service_name`** — the Cloud Run backend-service name suffix (`generate_url_map.py` builds
  `{service_name}-backend{-prod suffix}` from it) and the key you pass to
  `organizeme_chrome.registry.get_app(service_name)` (reading whichever `RegistrySource` your app
  configured — the Host's own in-process one, or every other consumer's fetched one, step 3).
- **`nav`** — `(path, label)` pairs. These render in the shared sidebar (merged across every
  registered app — see `organizeme_chrome.templating.register_chrome`, which builds
  `nav_items = [item for entry in list_apps() for item in entry.nav]`) **and** become URL-map
  path rules pointing at your service (step 2). Adding a nav item is simultaneously "show this in
  the sidebar" and "route this path to my backend" — one edit, both effects.
- **`settings_tabs`** — `(id, label)` pairs. Unlike `nav`, these don't get their own routes: the
  Host's `/settings` page (`app/pages/settings.py` in this repo) renders the tab bar and fetches
  each tab's *content* from your app at `GET /settings/{service_name}/{tab.id}` via HTMX
  (`hx-get`, `hx-trigger="load"`) — same-origin request through the shared LB domain, so the
  `organizeme_auth` cookie flows automatically. Your app owns the fragment route
  (`event-creator`'s is `app/pages/settings_fragments.py`); the Host never renders your tab's
  markup itself. If a tab needs no LB routing change, that's why: it's not a top-level nav path,
  it's a fragment fetched under a prefix your `api_prefixes` already covers.
- **`api_prefixes`** — every other route your app owns beyond its nav pages: your `/api/v1/*`
  surface and any `/settings/{service_name}/*` fragment routes. Feeds `generate_url_map.py` so the
  LB's path rules cover your **full** route surface, not just the pages that show up in the
  sidebar (this exact gap — API routes with no matching nav entry — was issue #178, fixed by
  adding this field).

**Concrete example if you're adding app #3** (say, a hypothetical `reminders` app with a single
`/reminders` nav page and a `Reminders` Settings tab, no other API routes beyond its own page):

```python
AppEntry(
    service_name="reminders",
    nav=[AppNavItem("/reminders", "Reminders")],
    settings_tabs=[SettingsTab("reminders", "Reminders")],
    api_prefixes=["/api/v1/reminders", "/settings/reminders"],
),
```

Add it to the `APPS` list in `app/core/registry.py` and redeploy the Host — that's the entire
Host-side change. No `packages/chrome` edit, no new `chrome-v*` tag, no consumer-repo pin bump:
every consumer's background refresh loop (step 3) picks up the new entry from
`GET /internal/app-registry.json` on its own next poll, without a deploy on its end. You only touch
`packages/chrome`/cut a new tag for changes to the shared *mechanism* itself (templates, the
registry-client code, `jwt_verify`, theme constants) — never for adding, removing, or editing a
hosted app's nav/Settings/API-prefix data.

## 2. Load-Balancer URL-map regeneration

`infra/gcp_lb/generate_url_map.py` turns the registry above into the shared LB's URL-map path
rules automatically:

```bash
uv run python -m infra.gcp_lb.generate_url_map          # QA, prints YAML
uv run python -m infra.gcp_lb.generate_url_map prod      # prod, renames every backend -prod
```

Rules, enforced at generation time (build-time guards, not runtime checks):

- The Host's own fixed routes (`HOST_PATHS` in that module — `/`, `/login`, `/register`,
  `/forgot-password`, `/reset-password`, `/profile`) always win a collision; they aren't sourced
  from the registry at all, since they're Host-owned and never delegated to a hosted app.
- Two non-Host apps claiming the same nav path, or the same `api_prefixes` entry, is a hard
  error — the generator refuses to produce an ambiguous URL map.
- Each `api_prefixes` entry also gets its own `/*` wildcard pattern (GCP's URL-map path matching
  is an exact-string prefix match, not path-segment-aware — see the module's own docstring for
  why `"/processing-runs"` and `"/api/v1/processing-runs"` need separate entries despite looking
  related).

You need a Cloud Run service (and its own Serverless NEG + backend service in the LB) to exist
**before** your registry entry's paths mean anything — that's a one-time manual `gcloud` step via
`infra/gcp_lb/provision.sh` (QA) / `provision-prod.sh` (prod), the same idempotent script that
provisioned `event-creator`'s NEG/backend in R6. Once your service and registry entry both exist,
re-running the generator and importing it (`gcloud compute url-maps import
organizeme{-prod}-url-map --source=<generated.yaml>`) is the only routing step for every
subsequent nav/prefix change — you never hand-edit LB resources directly.

## 3. The shared-chrome-package dependency

Every hosted app pins `organizeme-chrome` as a direct dependency, published by the Host's own CI
as a versioned GitHub Release wheel/sdist on `chrome-v*` tag push (a git-tag dependency pin, not
a private PyPI registry):

```toml
# event-creator's pyproject.toml, real pin as of R13:
"organizeme-chrome @ git+https://github.com/rustycoopes/organize-me@chrome-v0.4.0#subdirectory=packages/chrome",
```

What it gives you:

- **Chrome templates** (`chrome_base.html`, `chrome_authenticated_base.html`, the sidebar,
  `macros/chrome_tabs.html`) — extend these for every page your app renders; never hand-roll
  sidebar/header markup. `organizeme_chrome.templating.register_chrome(env, app_service_name)`
  wires your Jinja environment up to them and exposes `nav_items`/`settings_tabs`/theme globals.
- **The registry-read functions and client machinery** (`organizeme_chrome.registry.get_app`/
  `list_apps`, `organizeme_chrome.registry_client`'s `FetchedRegistrySource`/
  `fetch_registry_once`) — the *mechanism*, not the data. The actual app-registry data (nav items,
  Settings tabs, API prefixes for every hosted app) lives in the Host's own `app/core/registry.py`
  and is fetched at runtime (step 1) — `packages/chrome` ships no compiled-in copy of it.
- **The JWT-verify helper** (`organizeme_chrome.jwt_verify`) — see step 4.
- **Theme constants** (Tailwind/DaisyUI CDN links, `theme_attr`) for a consistent look with zero
  build step.

**Gotcha (R7, issue #207):** every page route that renders the shared chrome must pass the Host's
`dark_mode` preference — read via the `HostUser` cross-schema mapping (step 4's pattern, extended
to a Host-owned field) — into `theme_attr()`'s template context, not just the routes you remember
to check first. A route that forgets it always renders light-only regardless of the user's actual
Host Profile setting; this shipped unnoticed in `event-creator` for two parity slices before being
caught.

Bumping the pin is a **deliberate, explicit action in your own repo** — a `packages/chrome` code
change never silently changes what your app runs until you bump and redeploy. Historically (R6,
R11, pre-registry-decoupling) a stale pin also meant stale *registry data*, since the data itself
was compiled into the package — that specific failure mode is gone as of registry-decoupling
Slice 3 (organize-me#220): registry data (nav/Settings/API-prefix entries) now reaches you via the
background-refresh client (step 1), independent of your `organizeme-chrome` pin entirely. The pin
still matters for everything else this package ships — templates, `jwt_verify`, the registry
*client* code itself, theme constants — so still bump and redeploy deliberately whenever you want
one of those, but you no longer need to touch it just because a hosted app was added or its nav
changed.

## 4. The JWT-verify-helper usage pattern

A hosted app never handles login, sessions, or password verification — identity comes entirely
from verifying the Host-issued `organizeme_auth` cookie's JWT. `organizeme_chrome.jwt_verify`
(HS256, PyJWT-based, checks signature + expiry + the `fastapi-users:auth` audience only — no
`fastapi-users` import, no DB/network call) is the standalone helper every hosted app depends on
for this.

`event-creator`'s real implementation, `app/core/auth.py`:

```python
AUTH_COOKIE_NAME = "organizeme_auth"  # must match the Host's CookieTransport cookie_name

def current_user_id_optional(request: Request) -> uuid.UUID | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token is None:
        return None
    try:
        subject = verify_token(token, get_settings().jwt_secret)
        return uuid.UUID(subject)
    except (InvalidTokenError, ValueError):
        return None

def current_user_id(request: Request) -> uuid.UUID:
    user_id = current_user_id_optional(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id
```

Usage rules:

- **Page routes** depend on `current_user_id_optional` and redirect `None` to the Host's
  `/login` — a hosted app owns no login page of its own.
- **API routes** depend on `current_user_id` (raises 401) — the hosted-app equivalent of
  fastapi-users' `current_active_user`.
- Your Cloud Run service reads `JWT_SECRET` from the **exact same** GCP Secret Manager secret as
  the Host (`jwt-secret-{qa,prod}`, `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest`) — that
  byte-identical value is the entire SSO trust mechanism, not a coincidence.
- Never call the Host over the network to check a session, and never store your own session
  state — the JWT alone is the complete, stateless proof of identity.
- If your app needs to read Host-owned fields (e.g. `email`, `phone_number`) for display, do it
  via a read-only, cross-schema SQL mapping (`event-creator`'s `HostUser` — a SELECT-only ORM
  class over `host.users`, registered on your app's own `Base`/`MetaData` so
  `ForeignKey("host.users.id")` resolves), never a server-to-server API call to the Host at
  request time.

## 5. Test ownership

Unit tests and e2e tests live with the code they exercise, in the app's **own** repo:

- Every `event-creator` unit test (models, API endpoints, pipeline, storage providers, LLM
  prompt) lives in `event-creator/tests/`, and every `event-creator` Playwright spec lives in
  `event-creator/e2e/tests/` — none of it lives in this (`organize-me`) repo. R13 (#168) deleted
  the Host's now-redundant copies once `event-creator`'s own suite had equivalent (verified
  passing) coverage.
- **Exception: cross-repo boundary tests.** `e2e/tests/host-event-creator-boundary.spec.ts` stays
  in the Host, permanently — it asserts the *seam* between the two apps (logout at the Host
  clears the cookie a hosted app relies on; a hosted app's JWT-verify rejects a garbage/tampered
  token), not either app's internals. A future third app should get the same treatment: any test
  that exercises "does the Host's auth/cookie contract still hold from another app's point of
  view" belongs in the Host as a boundary spec; everything else belongs in that app's own repo.
- If your app's own CI wants to catch a boundary regression proactively (not just wait for the
  Host's CI to catch it), follow `event-creator`'s pattern: add a job that checks out the Host
  repo at a fixed ref and runs only the relevant boundary spec(s) against your freshly-deployed
  QA service (see `event-creator`'s `e2e-boundary-qa` CI job).

## 6. Quick-start checklist

Distilled from the above — everything you need for a brand-new hosted app from scratch. This is
the maintained, current version of this checklist; `host-integration-guide.md` keeps its own
older copy for historical continuity but points here as the canonical one.

1. Own git repo, own CI/CD (build → test → deploy) — never a Host build/redeploy.
2. Own `<app>-qa` / `<app>-prod` Cloud Run service pair, deployed **request-based** (Cloud Run's
   default billing model — CPU allocated only while handling a request): never pass
   `--no-cpu-throttling` and never set `--min-instances` on `gcloud run deploy`. This is a hard
   platform default, not a per-app judgment call — see
   `docs/adr/0001-event-creator-worker-cpu-throttling.md` for why the one prior exception
   (`event-creator` QA's `--no-cpu-throttling` experiment, to keep a Celery worker alive) was
   reverted rather than kept: any background/async work should push back to the service as a real
   HTTP request (Cloud Tasks push target) instead of trading into instance-based billing.
3. Own Artifact Registry Docker repo, created **with vulnerability scanning disabled**:
   ```bash
   gcloud artifacts repositories create <app-slug> \
     --repository-format=docker \
     --location=<region> \
     --disable-vulnerability-scanning
   ```
   (one-time manual step, before the first `docker push` in your deploy workflow can succeed).
4. Pinned `organizeme-chrome` dependency (step 3).
5. An entry in the Host's `app/core/registry.py` (step 1) — Host-repo PR, reviewed like any other
   Host change — plus your own repo's `configure_client_registry_source()` +
   `start_registry_refresh_task()`/`stop_registry_refresh_task()` wiring in your `lifespan` (step
   3), so your app actually reads that entry (and everyone else's) at runtime.
6. Own Postgres schema, own independent Alembic history
   (`version_table_schema = <your_schema>`) — never write to another app's schema, and never
   more than a `REFERENCES`-only grant back to `host.users.id` if you need a real FK.
7. `GCP_SA_KEY` and your own `SUPABASE_QA_URL`/`SUPABASE_PROD_URL` as GitHub Actions secrets in
   **your own** repo.
8. `--set-secrets=JWT_SECRET=jwt-secret-{qa,prod}:latest` on your deploy step (step 4).
9. If you store third-party credentials at rest: `--set-secrets=ENCRYPTION_KEY=encryption-key-
   {qa,prod}:latest`, encrypted with a `CredentialCipher` pattern (see `event-creator`'s
   `app/core/security.py` — the Host's own copy was removed in this same slice, since it stored
   no such credentials of its own) — never plaintext.
10. No login/session/registration/password code of your own, ever (step 4).
11. No server-to-server call to the Host at request time, for anything (step 4).
12. Regenerate and import the LB URL map once your service and registry entry both exist (step 2).
13. Your own `tests/` and `e2e/` — nothing shared except the boundary spec (step 5).
