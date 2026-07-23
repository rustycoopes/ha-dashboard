---
name: new-hosted-app
description: >-
  Scaffold a brand-new OrganizeMe hosted-app repo — folder structure, FastAPI/CI skeleton,
  CLAUDE.md, every skill and agent from this repo, and the platform docs
  (how-to-add-a-hosted-app.md, host-integration-guide.md, feature-workflow.md,
  secrets-and-accounts.md, creating-prerequisites.md) — then creates the repo in the GitHub org
  and pushes it. Use this whenever the user wants to "start a new repo/app for organize-me",
  "stand up hosted app #N", "scaffold a new service" for the platform, or start implementing
  Slice 1 of a feature whose WBS calls for "Repo & infra setup" (e.g. doc-library's Slice 1). If
  a `docs/features/<app-slug>/` directory already exists for the app (PRD/TDD/WBS from an earlier
  `/to-prd`/`/to-design`/`/to-wbs` pass), this skill brings it into the new repo automatically —
  trigger it as soon as that feature's planning is approved and it's time to actually stand up
  the repo, don't wait for the user to spell out every setup step.
---

# New Hosted App

Stands up the local-repo half of "add a hosted app to OrganizeMe" (see
`docs/how-to-add-a-hosted-app.md` in this repo for the full platform pattern) — everything that's
pure file/repo work, done once via a script instead of hand-copied file by file. It deliberately
does **not** touch GCP (Secret Manager, Cloud Run provisioning, the Load Balancer) or the Host's
`packages/chrome/src/organizeme_chrome/registry.py` — those stay manual/human steps, and the skill
prints them as a checklist at the end using the docs it just copied in.

## Why a script, not hand-written files

Every hosted app needs the same ~25 boilerplate files (FastAPI skeleton, Alembic env, CI/CD
workflows, JWT-verify auth module, db session/url helpers) with only the app's name and schema
changed. `scripts/scaffold_repo.py` generates all of it deterministically from templates in
`assets/templates/` — faster and less error-prone than writing each file fresh per app, and it's
already been validated end-to-end (dependencies resolve, `mypy` passes, git history is clean).
Use the script; don't hand-write these files again.

## Workflow

1. **Get the app slug and title.** If the user names the app but hasn't run `/grilling` →
   `/to-prd` → `/to-design` → `/to-wbs` for it yet, that's fine — this skill only needs a
   kebab-case slug (e.g. `doc-library`) and a human-readable title (e.g. "Doc Library"). If
   `docs/features/<slug>/` already exists in this repo (check with `ls docs/features`), the slug
   is already decided — use it, don't ask again.

2. **Dry-run the script first** to show the user exactly what will be created, before writing
   anything:

   ```
   python .claude/skills/new-hosted-app/scripts/scaffold_repo.py <app-slug> "<App Title>" --dry-run
   ```

   This prints the full file plan (every write/copy it's about to do) with zero side effects.
   Skim it and flag anything surprising (e.g. the `docs/features/<slug>` line shows "skip" —
   confirm with the user whether that's expected, since it usually means the slug doesn't match
   an existing feature directory exactly).

3. **Run it for real (no `--push` yet)** to actually write the files and create the local git repo
   with an initial commit:

   ```
   python .claude/skills/new-hosted-app/scripts/scaffold_repo.py <app-slug> "<App Title>"
   ```

   By default this writes to a sibling directory of this repo (`../<app-slug>`, matching where
   `event-creator` lives relative to `organize-me`). Pass `--dest <path>` to override.

4. **Show the user what landed** — at minimum, list the top-level structure (`ls`/`tree`-style)
   and point out the three things worth a second look before pushing:
   - `pyproject.toml`'s `organizeme-chrome` pin (auto-detected from the latest local `chrome-v*`
     tag — flag it if the script warned it couldn't detect one).
   - Whether `docs/features/<slug>/` actually came across (only happens if that directory existed
     in this repo at scaffold time).
   - `CLAUDE.md`, `.claude/skills/*`, `.claude/agents/*.md` are copied verbatim, unmodified — this
     is intentional per how the user asked for this skill to work; don't "helpfully" edit them
     for the new app unless asked.

5. **Creating the GitHub repo and pushing is a separate, explicit step the user confirms.**
   Creating a public repo under someone's GitHub account and pushing to it is a real,
   externally-visible action — never chain straight from scaffolding into `--push` without
   showing the plan and getting a clear go-ahead first, even if the user's original request
   sounded like they wanted the whole thing done in one shot. Once they confirm:

   ```
   python .claude/skills/new-hosted-app/scripts/scaffold_repo.py <app-slug> "<App Title>" --push
   ```

   (Re-running is safe — pass `--force` if the destination directory already exists from step 3;
   the script won't re-scaffold over a non-empty directory otherwise.) This runs
   `gh repo create <owner>/<app-slug> --public --source=. --remote=origin --push` under the hood.
   Defaults: owner `rustycoopes`, visibility `public` (matching both `organize-me` and
   `event-creator` today) — override with `--github-owner`/`--visibility` if this app should
   differ.

6. **Print the manual next-steps checklist.** The script does not and cannot do GCP/Secret
   Manager/Load-Balancer work — after it finishes, tell the user what's left, pointing at the docs
   now living in the new repo's own `docs/` directory (`how-to-add-a-hosted-app.md` has the full
   playbook; `secrets-and-accounts.md` has the secret-flow diagram). At minimum:
   - `GCP_SA_KEY`, `SUPABASE_QA_URL`, `SUPABASE_PROD_URL` as GitHub Actions secrets in the **new**
     repo (never inherited from the Host).
   - Confirm the shared deploy service account already has `secretmanager.secretAccessor` on
     `jwt-secret-{qa,prod}` (true today for every existing service, but worth a `gcloud` check,
     not an assumption).
   - Create the app's Artifact Registry Docker repo **with vulnerability scanning disabled**
     (`gcloud artifacts repositories create <app-slug> --repository-format=docker
     --location=<region> --disable-vulnerability-scanning`) — needed before the generated
     workflows' first `docker push` can succeed.
   - Every Cloud Run service for the app (`<app>-qa` and `<app>-prod`) stays **request-based**
     billing: never add `--no-cpu-throttling` or `--min-instances` to `gcloud run deploy` — this is
     a platform-wide default, not a per-app choice (see
     `docs/adr/0001-event-creator-worker-cpu-throttling.md` in the copied docs).
   - A new Postgres schema for the app, with its own independent Alembic history
     (`version_table_schema` — already wired into the generated `migrations/env.py`).
   - Only once the service is deployed and reachable: the Host-repo registry PR
     (`packages/chrome/src/organizeme_chrome/registry.py`) and Load Balancer provisioning
     (`infra/gcp_lb/provision.sh` + `generate_url_map.py` + `gcloud compute url-maps import`).
   If the feature has a WBS (`docs/features/<slug>/WBS/`), these map directly onto its "Repo &
   infra setup" and "SSO-trust tracer bullet" slices — point the user there if it exists rather
   than re-deriving the checklist from scratch.

## What the script does NOT do (by design)

- No GCP calls of any kind (Secret Manager, Cloud Run, Load Balancer) — those need a human with
  `gcloud` access and judgment about environment-specific values.
- No edit to the Host repo's `registry.py` — that's a reviewed PR in `organize-me`, not a side
  effect of scaffolding a different repo.
- No app-specific business logic — the generated `app/pages/`, `app/api/v1/`, `app/models/`,
  `app/schemas/` packages are empty (just `__init__.py`). This skill's job ends at "a working,
  deployable skeleton with health check, auth, and CI wired up" — the app's actual feature slices
  (per its own WBS) are `/to-implementation`'s job, run from inside the new repo.

## Files

- `scripts/scaffold_repo.py` — does all the work; run with `--dry-run` first, `-h` for full CLI
  options (`--dest`, `--github-owner`, `--gcp-project`, `--gcp-region`, `--chrome-tag`,
  `--visibility`, `--push`, `--force`).
- `assets/templates/` — every templated file the script renders (`{{APP_SLUG}}`, `{{APP_TITLE}}`,
  `{{APP_SCHEMA}}`, `{{GITHUB_OWNER}}`, `{{CHROME_TAG}}`, `{{GCP_PROJECT_ID}}`, `{{GCP_REGION}}`
  placeholders). Update these if the platform's own conventions change (e.g. a new required env
  var every hosted app needs) — they were sourced from `event-creator`'s real files, trimmed to
  the generic subset every app needs (no OAuth/Twilio/Gemini-specific scaffolding, since those are
  `event-creator`-specific, not part of the platform pattern itself).
