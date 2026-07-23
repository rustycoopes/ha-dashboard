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

- [x] `ha-dashboard` repo exists with a working CI/CD pipeline (build, test, smoke-test, deploy
      stages all green).
- [x] The CI smoke-test job fails the pipeline (doesn't just warn) on a deliberately broken
      migration or a Dockerfile that fails to boot — verified once by intentionally breaking one
      and confirming the pipeline goes red.
- [x] A deploy of the skeleton app succeeds and the health-check route responds at
      `ha-dashboard-prod`'s Cloud Run `*.run.app` URL.
- [x] `GCP_SA_KEY` and `SUPABASE_PROD_URL` are set as GitHub Actions secrets in the new repo (not
      inherited from the Host repo). No `SUPABASE_QA_URL` is present.
- [x] `ha_dashboard` Postgres schema exists with its own independent Alembic history
      (`version_table_schema=ha_dashboard`), verified by running an empty migration successfully.
- [x] The shared deploy SA's `secretmanager.secretAccessor` role on `jwt-secret-prod` and
      `encryption-key-prod` is confirmed (not assumed) before the first real deploy.

## Testing

Infra/CI verification, not application-level tests: a green CI run (including the smoke-test job)
is the acceptance signal for the pipeline; a successful `alembic upgrade head` against the
throwaway CI Postgres (creating no tables yet) verifies the schema/migration-history setup.
No unit or HTTP-level tests are meaningful yet since there's no feature code — `tests/test_health.py`
(a trivial 200-OK check, matching `doc-library`'s/`event-creator`'s own) is the only test this
slice needs.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

## Delivered (2026-07-23, issue #1, branch `feature/slice-1-repo-and-infra-setup`)

The `/new-hosted-app` scaffold had already landed the repo skeleton directly on `main` (commit
`2f74536`) before this issue's `/to-implementation` pass started, but it copied
`event-creator`'s/`doc-library`'s standard QA+prod CI/CD template verbatim — which doesn't fit
this app's deliberate no-QA architecture, and left the pipeline unable to run at all. This
slice's work was fixing that scaffold, not building fresh:

- Added the missing `uv.lock` — the scaffold commit omitted it, breaking `uv sync --frozen` in
  every CI run before it reached any real step (this is what run #30007825550 hit).
- Rewrote `ci.yml` (single `test` job against a throwaway Postgres service container, no QA
  deploy — there's nothing to deploy to pre-merge) and `deploy.yml` (added a `smoke-test` job that
  builds the real production image, runs it against a fresh throwaway Postgres, applies the
  Alembic migration, and hits the health check; `deploy-prod` now depends on it via `needs:`).
- Added `migrations/versions/0001_create_ha_dashboard_schema.py`: creates the `ha_dashboard`
  schema and an `ha_dashboard_app` role, mirroring `doc_library`'s own baseline
  (`0001_create_doc_library_schema.py`) minus the `host.users` REFERENCES grant — no cross-schema
  FK exists yet, and a throwaway CI Postgres has no `host` schema to reference anyway.
- **Diverged from plan / hit a real bug not anticipated in the WBS** — the same chicken-and-egg
  problem `doc-library`'s Slice 1 hit: Alembic creates its own version table in
  `version_table_schema` *before* running the first migration, so on a database that's never seen
  this app before, `alembic upgrade head` failed with `InvalidSchemaNameError: schema
  "ha_dashboard" does not exist` even though migration 0001 itself creates that schema. First fix
  attempt (a bare `connection.execute("CREATE SCHEMA IF NOT EXISTS ...")` inside
  `do_run_migrations`) introduced a second, more serious bug caught by code review before merge:
  leaving the connection mid-transaction flips Alembic's `_in_external_transaction` check to
  `True`, so Alembic assumes the caller owns the transaction and never commits anything itself —
  silently rolling back the schema, the role/grants, and the `alembic_version` row on every
  `alembic upgrade head` run, while the command still exited 0. Fixed by moving the bootstrap plus
  an explicit `await connection.commit()` into `run_async_migrations`, matching `doc-library`'s
  own identical fix exactly. Added an explicit post-migration persistence check (queries
  `ha_dashboard.alembic_version` directly) to every migration step in both workflows as
  defense-in-depth, since nothing else in the pipeline (no tables yet, `/health` never touches the
  DB) would otherwise have noticed a migration that silently no-ops.
- Restored `pytest`/`mypy` to `deploy.yml`'s `smoke-test` job (an earlier draft had dropped them,
  leaving only the Alembic/Docker/health-check checks) and added a short retry loop to
  `deploy-prod`'s final health check for parity with `smoke-test`'s.
- Confirmed manually (read-only/one-time infra checks, not part of the code diff): the shared
  deploy SA already has `secretmanager.secretAccessor` on `jwt-secret-prod` and
  `encryption-key-prod`; created the `ha-dashboard` Artifact Registry Docker repo (vulnerability
  scanning disabled), which didn't exist yet and is required before `deploy-prod`'s `docker push`
  can succeed; removed two stray GitHub secrets (`SUPABASE_QA_URL`, `ENCRYPTION_KEY`) that had
  been set alongside the two required ones, restoring the exact secret set the acceptance
  criteria call for.
- Also fixed several scaffold-copy artifacts unrelated to CI/CD but caught along the way: a
  missing `.env.local.example`, a missing `docs/changelog.md` (both referenced by
  `CLAUDE.md`/`README.md` but never created), and stale QA-tier/broken-doc-link references in
  `CLAUDE.md`, `README.md`, `app/core/config.py`, and `tests/conftest.py` left over from the
  scaffold's copy of another repo's docs.
- First-ever deploy of `ha-dashboard-prod` succeeded end to end: `smoke-test` and `deploy-prod`
  both green, the real migration against Supabase prod persisted at revision
  `0001_create_ha_dashboard_schema`, and the health check responded `{"status":"ok"}` at
  `https://ha-dashboard-prod-n7cbjtsj5a-nn.a.run.app/health`.
