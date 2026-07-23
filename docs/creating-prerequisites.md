# Creating Prerequisites — Setup Log

**Date:** 2026-06-30
**Purpose:** Record of the decisions and steps taken to satisfy the "Prerequisites Before Slice 1 Begins" checklist in `docs/features/original-organize-me/implementation-plan.md`, and the related GitHub issues (#1, #2, #6).

---

## Deploy strategy decision

Cloud Run services are deployed via **image-based deploys driven by GitHub Actions**, not Cloud Run's native "continuously deploy from a repository" (Cloud Build trigger) feature.

**Why:** `ci.yml`/`deploy.yml` already run tests + mypy before deploying (per the implementation plan). Native Cloud Build continuous deploy would bypass that gate and create a second, parallel deploy path. Keeping GitHub Actions as the single deploy path means tests always gate what reaches QA/prod.

**Flow:** GitHub Actions builds the Docker image → pushes to Artifact Registry → `gcloud run deploy` with that image tag.

---

## GitHub Actions secrets (issue reference: prerequisites list)

Secrets configured via `gh secret set`:

| Secret | Source |
|---|---|
| `GCP_SA_KEY` | Service account `github-deployer` (roles: `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`), key generated via `gcloud iam service-accounts keys create` |
| `SUPABASE_QA_URL` / `SUPABASE_PROD_URL` | Supabase project connection strings |
| `UPSTASH_REDIS_URL` | Upstash Redis database connection URL |
| `GEMINI_API_KEY` | Google AI Studio |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Twilio console |
| `RESEND_API_KEY` | Resend dashboard |

Note: the service account key is a long-lived credential. Workload Identity Federation (no key file, short-lived tokens) was noted as a more secure alternative, not yet adopted.

Considered but not yet decided: splitting secrets across GitHub **Environments** (`qa`, `prod`) instead of flat repo-level secrets, to allow per-environment values and a manual approval gate on prod deploys.

---

## `.env.local`

Created at the repo root (already covered by `.gitignore` — never committed). Holds local dev config:

- App: `APP_ENV`, `SECRET_KEY`, `BASE_URL`
- Cloud Run service URLs: `CLOUD_RUN_QA_URL`, `CLOUD_RUN_PROD_URL`
- Database: `DATABASE_URL` (points at Supabase QA — no local Docker for DB)
- Redis: `REDIS_URL` (Upstash, shared local/prod instance — no local Docker for Redis)
- Auth: `JWT_SECRET`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`
- LLM: `GEMINI_API_KEY`, `GEMINI_MODEL`
- Storage (Google Drive): `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REDIRECT_URI`
- Email: `RESEND_API_KEY`
- SMS: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- Internal: `TRIGGER_SCAN_SHARED_SECRET`

---

## Issue #2 — Artifact Registry + Cloud Run (QA + prod)

- [x] Artifact Registry Docker repository created

**Policy for any new Artifact Registry repo created after this one:** always pass
`--disable-vulnerability-scanning` at creation time (`gcloud artifacts repositories create <repo>
--repository-format=docker --location=<region> --disable-vulnerability-scanning`). The
`organizeme` repo created below predates this policy and was not created with the flag.
- [x] QA Cloud Run service created (`organizeme-qa`)
- [x] Prod Cloud Run service created (`organizeme-prod`)
- [x] Service URLs noted in `.env.local`

Both services were stood up with a placeholder image (`us-docker.pkg.dev/cloudrun/container/hello`) so the auto-generated `*.run.app` URLs would exist ahead of real app code — `deploy.yml` overwrites them with the real image once Slice 1 lands.

Key settings:
- Region: `northamerica-northeast1`
- `--allow-unauthenticated` (public web app; auth handled by FastAPI-Users, not GCP IAM)
- `--port=8000`
- `--timeout=3600` (Cloud Run default is 300s; raised to accommodate long-lived SSE connections for the pipeline progress page)
- `--memory=1Gi` (FastAPI + Celery worker share the container via supervisord)
- QA: `--min-instances=0` (cost savings, only hit during PR review)
- Prod: `--min-instances=1` (avoid cold starts for real users)

**Superseded:** this `--min-instances=1` setting was later removed. The platform-wide policy as of
`docs/adr/0001-event-creator-worker-cpu-throttling.md` is that every Cloud Run service — QA and
prod alike — stays on plain request-based billing: no `--min-instances`, no `--no-cpu-throttling`.
Kept here for historical accuracy only; don't copy this setting into a new service.

Resulting URLs (stored in `.env.local`):
- QA: `https://organizeme-qa-170051512639.northamerica-northeast1.run.app`
- Prod: `https://organizeme-prod-170051512639.northamerica-northeast1.run.app`

The `github-deployer` service account was granted `roles/run.developer` scoped to each service.

---

## Issue #6 — Google OAuth app

Used for two purposes: Google login (FastAPI-Users) and Google Drive storage connection.

Steps taken:
1. Enabled **Google Drive API** and **People API** on the GCP project.
2. Configured the **OAuth consent screen** (External user type, app name `OrganizeMe`, test users added while in Testing status).
3. Added scopes: `openid`, `userinfo.email`, `userinfo.profile`, and `https://www.googleapis.com/auth/drive` (full Drive scope — required because the `StorageProvider` interface lists/moves/downloads files across arbitrary user folders, not just app-created ones, so the narrower `drive.file` scope isn't sufficient).
4. Created an **OAuth 2.0 Client ID** (Web application) named `OrganizeMe Web Client`.
5. Added authorized redirect URIs — initially just localhost (QA/prod Cloud Run URLs didn't exist yet):
   ```
   http://localhost:8000/api/v1/auth/google/callback
   http://localhost:8000/api/v1/storage-config/google-drive/callback
   ```
6. After issue #2 produced the Cloud Run URLs, returned to the same OAuth client and added:
   ```
   https://organizeme-qa-170051512639.northamerica-northeast1.run.app/api/v1/auth/google/callback
   https://organizeme-qa-170051512639.northamerica-northeast1.run.app/api/v1/storage-config/google-drive/callback
   https://organizeme-prod-170051512639.northamerica-northeast1.run.app/api/v1/auth/google/callback
   https://organizeme-prod-170051512639.northamerica-northeast1.run.app/api/v1/storage-config/google-drive/callback
   ```
7. Client ID and secret stored in `.env.local` (`GOOGLE_OAUTH_CLIENT_ID`/`SECRET` and `GOOGLE_DRIVE_CLIENT_ID`/`SECRET` — same client reused for both purposes).

**Outstanding item:** the `drive` scope is restricted/sensitive. The app is currently in "Testing" publishing status (max 100 test users, no review needed). Before public launch, Google requires an **OAuth verification review** (privacy policy, possibly a demo video, days-to-weeks turnaround). This is not a blocker for Slice 1–2 development but should be tracked as a pre-launch dependency.

---

## Status of prerequisites checklist

From `docs/features/original-organize-me/implementation-plan.md` → "Prerequisites Before Slice 1 Begins":

- [x] GCP project created, billing linked, required APIs enabled (issue #1)
- [x] Artifact Registry repo + two Cloud Run services (QA + prod) provisioned (issue #2)
- [x] GitHub Actions secrets configured
- [ ] Supabase: two projects (QA + prod), connection strings noted — QA confirmed in `.env.local`; prod still pending
- [x] Upstash Redis: one database, connection URL noted
- [x] Google OAuth app registered (for Drive + auth) — client ID + secret (issue #6)
- [ ] Resend account + domain verified — API key present in `.env.local`; domain verification not yet confirmed
- [ ] Twilio trial account + phone number — credentials present in `.env.local`; trial/production status not yet confirmed
- [x] Gemini API key from Google AI Studio
