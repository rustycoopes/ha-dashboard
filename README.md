# HA Dashboard

An OrganizeMe hosted app — its own repo, own Cloud Run service(s), and own Postgres schema
(`ha_dashboard`). Trusts the Host-issued JWT cookie for identity; never handles login, sessions,
or passwords itself. See `docs/how-to-add-a-hosted-app.md` for the platform pattern this repo
follows, and `CLAUDE.md` for how to work in this codebase.

## Setup

```
uv sync --group dev
```

Copy `.env.local.example` to `.env.local` (never commit `.env.local` — see `.gitignore`) and fill
in `DATABASE_URL`/`JWT_SECRET`. ha-dashboard has no QA Supabase tier (see
`docs/adr/ha-dashboard-no-qa-environment.md` in the organize-me repo) — point `DATABASE_URL` at
your own local Postgres instance for local development.

## Running locally

```
uv run uvicorn app.main:app --reload --port 8000
```

## Tests

```
uv run pytest
uv run mypy app tests
```

## Migrations

```
uv run alembic revision --autogenerate -m "..."
uv run alembic upgrade head
```

## Deployment

Unlike every other hosted app on the platform, ha-dashboard has **no QA Cloud Run tier** — see
`docs/adr/ha-dashboard-no-qa-environment.md` (organize-me repo) for why. In its place:

- `.github/workflows/ci.yml` (on PR): runs pytest/mypy/Alembic against a throwaway Postgres
  service container local to the CI job — nothing is deployed.
- `.github/workflows/deploy.yml` (on push to `main`): a `smoke-test` job builds the production
  Docker image, runs it against a fresh throwaway Postgres, applies the Alembic migrations, and
  hits its health check — the pipeline's only pre-production gate. Only if that passes does
  `deploy-prod` apply the real migration against Supabase prod and deploy to `ha-dashboard-prod`.

See `docs/host-integration-guide.md` and `docs/secrets-and-accounts.md` for the manual setup
(GitHub Actions secrets, GCP Secret Manager grants, Load Balancer registration) this pipeline
depends on.
