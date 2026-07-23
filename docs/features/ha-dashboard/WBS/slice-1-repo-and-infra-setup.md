# Slice 1 — Repo & infra setup

> Part of the `ha-dashboard` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** A new `ha-dashboard` repo whose CI/CD pipeline builds, tests, and deploys a minimal
FastAPI skeleton straight to its own prod Cloud Run service — with every secret it will ever need
already in place and a CI-level smoke test guarding the deploy pipeline — before any real page or
endpoint exists.

## What to build

Stand up the `ha-dashboard` repo and its deploy pipeline, with no feature logic yet — pure
scaffolding so later slices can focus entirely on the SSO seam, HA integration, and dashboard UI,
not infra.

- New GitHub repo `ha-dashboard`, FastAPI project skeleton (mirroring `doc-library`'s/
  `event-creator`'s repo layout: `app/`, `tests/`, `migrations/`, `pyproject.toml`, `Dockerfile`,
  `.github/workflows/`) with a trivial health-check route and no other behavior yet.
- CI workflow (build → test → deploy) targeting `ha-dashboard-prod` directly — **no QA stage**,
  per [`ADR: no QA environment`](../../../adr/ha-dashboard-no-qa-environment.md). In its place, a
  CI job ahead of the deploy step that builds the production image, runs it against a throwaway
  CI-local Postgres, runs `alembic upgrade head`, and hits the health check — this is the
  pipeline's only pre-production gate, so it must actually block a bad deploy, not just log a
  warning.
- GitHub Actions secrets set in the new repo: `GCP_SA_KEY` (copied from the existing shared deploy
  service account — no new GCP SA needed), `SUPABASE_PROD_URL` only (no `SUPABASE_QA_URL` — there
  is no QA tier).
- Confirm (don't recreate) that the shared deploy SA already has `secretmanager.secretAccessor` on
  `jwt-secret-prod` and `encryption-key-prod` — both needed from this app's first real deploy
  onward (this app *does* need `ENCRYPTION_KEY`, unlike `doc-library` — don't cargo-cult that
  omission from `doc-library`'s Slice 1).
- Own Postgres schema (`ha_dashboard`) created in the shared Supabase instance, with its own
  Alembic history (`version_table_schema=ha_dashboard`) — no tables yet, just the schema and
  migration scaffolding wired up.

## Design notes

Implements the TDD's "Deployment / Cloud Run" section and
[`ADR: no QA environment`](../../../adr/ha-dashboard-no-qa-environment.md) in full. See
[`host-integration-guide.md`](../../../host-integration-guide.md)'s manual-steps checklist and
[`how-to-add-a-hosted-app.md`](../../../how-to-add-a-hosted-app.md) for the general pattern this
follows — this slice does *not* yet touch the Host repo's registry or the Load Balancer (that's
Slice 2's job); it only needs the service reachable at its own `*.run.app` URL for smoke-testing.

Exact throwaway-Postgres mechanism for the CI smoke test (service container vs. `testcontainers`
vs. a simpler SQLite-for-migration-only check) is left to this slice's implementation — the ADR
only requires that *some* pre-deploy migration/boot check exists and actually gates the deploy.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] `ha-dashboard` repo exists with a working CI/CD pipeline (build, test, smoke-test, deploy
      stages all green).
- [ ] The CI smoke-test job fails the pipeline (doesn't just warn) on a deliberately broken
      migration or a Dockerfile that fails to boot — verified once by intentionally breaking one
      and confirming the pipeline goes red.
- [ ] A deploy of the skeleton app succeeds and the health-check route responds at
      `ha-dashboard-prod`'s Cloud Run `*.run.app` URL.
- [ ] `GCP_SA_KEY` and `SUPABASE_PROD_URL` are set as GitHub Actions secrets in the new repo (not
      inherited from the Host repo). No `SUPABASE_QA_URL` is present.
- [ ] `ha_dashboard` Postgres schema exists with its own independent Alembic history
      (`version_table_schema=ha_dashboard`), verified by running an empty migration successfully.
- [ ] The shared deploy SA's `secretmanager.secretAccessor` role on `jwt-secret-prod` and
      `encryption-key-prod` is confirmed (not assumed) before the first real deploy.

## Testing

Infra/CI verification, not application-level tests: a green CI run (including the smoke-test job)
is the acceptance signal for the pipeline; a successful `alembic upgrade head` against the
throwaway CI Postgres (creating no tables yet) verifies the schema/migration-history setup.
No unit or HTTP-level tests are meaningful yet since there's no feature code — `tests/test_health.py`
(a trivial 200-OK check, matching `doc-library`'s/`event-creator`'s own) is the only test this
slice needs.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
