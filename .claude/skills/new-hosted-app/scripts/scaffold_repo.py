#!/usr/bin/env python3
"""Scaffold a new OrganizeMe hosted-app repo: folder structure, FastAPI/CI skeleton, CLAUDE.md,
skills/agents, and the platform docs a new hosted app needs — following the pattern documented
in docs/how-to-add-a-hosted-app.md.

This script only touches the local filesystem and (optionally, with --push) creates/pushes a
GitHub repo via `gh`. It never touches GCP, Secret Manager, or the Host's app-registry — those
remain manual/human steps, printed at the end as a checklist.

Usage:
    uv run python scaffold_repo.py <app-slug> "<App Title>" [options]

Run with --dry-run first to see the plan without writing anything.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_GITHUB_OWNER = "rustycoopes"
DEFAULT_GCP_PROJECT_ID = "gen-lang-client-0791944342"
DEFAULT_GCP_REGION = "northamerica-northeast1"

# Docs every new hosted app needs a copy of, relative to the source repo root.
DOCS_TO_COPY = [
    "docs/how-to-add-a-hosted-app.md",
    "docs/host-integration-guide.md",
    "docs/feature-workflow.md",
    "docs/secrets-and-accounts.md",
    "docs/creating-prerequisites.md",
]

SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def find_source_repo() -> Path:
    """This script lives at <source_repo>/.claude/skills/new-hosted-app/scripts/scaffold_repo.py."""
    here = Path(__file__).resolve()
    candidate = here.parents[4]
    if not (candidate / "CLAUDE.md").exists() or not (candidate / ".claude").is_dir():
        fail(
            f"couldn't locate the source repo root from {here} "
            "(expected <repo>/.claude/skills/new-hosted-app/scripts/scaffold_repo.py)"
        )
    return candidate


def latest_chrome_tag(source_repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_repo), "tag", "-l", "chrome-v*"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    tags = [t for t in result.stdout.splitlines() if t.strip()]
    if not tags:
        return None

    def version_key(tag: str) -> tuple[int, ...]:
        parts = tag.removeprefix("chrome-v").split(".")
        return tuple(int(p) for p in parts if p.isdigit())

    return sorted(tags, key=version_key)[-1]


def real_skill_dirs(source_repo: Path) -> list[Path]:
    """Only directories directly containing a SKILL.md — excludes eval-workspace/scratch dirs
    like next-issue-workspace that live alongside real skills in .claude/skills/ but aren't ones.
    """
    skills_dir = source_repo / ".claude" / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def render(template_path: Path, substitutions: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write_file(path: Path, content: str, dry_run: bool) -> None:
    print(f"  write  {path}")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    print(f"  copy   {src} -> {dst}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, dry_run: bool) -> None:
    print(f"  copy   {src}/ -> {dst}/")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def scaffold(args: argparse.Namespace) -> Path:
    source_repo = find_source_repo()
    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"

    app_schema = args.app_slug.replace("-", "_")
    chrome_tag = args.chrome_tag or latest_chrome_tag(source_repo)
    if chrome_tag is None:
        print(
            "warning: couldn't auto-detect the latest chrome-v* tag from the local git history; "
            "using a placeholder — update pyproject.toml's organizeme-chrome pin by hand.",
            file=sys.stderr,
        )
        chrome_tag = "chrome-v0.0.0-REPLACE-ME"

    subs = {
        "APP_SLUG": args.app_slug,
        "APP_TITLE": args.app_title,
        "APP_SCHEMA": app_schema,
        "GITHUB_OWNER": args.github_owner,
        "CHROME_TAG": chrome_tag,
        "GCP_PROJECT_ID": args.gcp_project,
        "GCP_REGION": args.gcp_region,
    }

    dest = args.dest
    print(f"Scaffolding {args.app_title!r} ({args.app_slug}) at {dest}")
    print(f"  (source repo: {source_repo}, organizeme-chrome pin: {chrome_tag})\n")

    if dest.exists() and any(dest.iterdir()):
        if not args.force:
            fail(f"{dest} already exists and is not empty (pass --force to reuse it anyway)")

    # --- generated app skeleton ---------------------------------------------------------
    write_file(dest / "pyproject.toml", render(templates / "pyproject.toml.template", subs), args.dry_run)
    write_file(dest / "Dockerfile", (templates / "Dockerfile").read_text(encoding="utf-8"), args.dry_run)
    write_file(dest / "alembic.ini", (templates / "alembic.ini").read_text(encoding="utf-8"), args.dry_run)
    write_file(dest / ".gitignore", (templates / "gitignore").read_text(encoding="utf-8"), args.dry_run)
    write_file(dest / "README.md", render(templates / "README.md.template", subs), args.dry_run)

    write_file(dest / "app" / "__init__.py", "", args.dry_run)
    write_file(dest / "app" / "main.py", render(templates / "app" / "main.py.template", subs), args.dry_run)
    for pkg in ("core", "db", "pages", "api", "api/v1", "models", "schemas"):
        write_file(dest / "app" / pkg / "__init__.py", "", args.dry_run)
    write_file(
        dest / "app" / "core" / "auth.py",
        (templates / "app" / "core" / "auth.py").read_text(encoding="utf-8"),
        args.dry_run,
    )
    write_file(
        dest / "app" / "core" / "config.py",
        render(templates / "app" / "core" / "config.py.template", subs),
        args.dry_run,
    )
    for name in ("base.py", "session.py", "url.py"):
        write_file(
            dest / "app" / "db" / name,
            (templates / "app" / "db" / name).read_text(encoding="utf-8"),
            args.dry_run,
        )

    write_file(dest / "migrations" / "__init__.py", "", args.dry_run)
    write_file(
        dest / "migrations" / "env.py",
        render(templates / "migrations" / "env.py.template", subs),
        args.dry_run,
    )
    write_file(
        dest / "migrations" / "script.py.mako",
        (templates / "migrations" / "script.py.mako").read_text(encoding="utf-8"),
        args.dry_run,
    )
    write_file(dest / "migrations" / "versions" / ".gitkeep", "", args.dry_run)

    write_file(dest / "tests" / "__init__.py", "", args.dry_run)
    write_file(
        dest / "tests" / "conftest.py",
        render(templates / "tests" / "conftest.py.template", subs),
        args.dry_run,
    )
    write_file(
        dest / "tests" / "test_health.py",
        (templates / "tests" / "test_health.py").read_text(encoding="utf-8"),
        args.dry_run,
    )

    write_file(
        dest / ".github" / "workflows" / "ci.yml",
        render(templates / "github" / "workflows" / "ci.yml.template", subs),
        args.dry_run,
    )
    write_file(
        dest / ".github" / "workflows" / "deploy.yml",
        render(templates / "github" / "workflows" / "deploy.yml.template", subs),
        args.dry_run,
    )

    # --- copied from the source (Host) repo ---------------------------------------------
    copy_file(source_repo / "CLAUDE.md", dest / "CLAUDE.md", args.dry_run)

    for skill_dir in real_skill_dirs(source_repo):
        copy_tree(skill_dir, dest / ".claude" / "skills" / skill_dir.name, args.dry_run)

    agents_dir = source_repo / ".claude" / "agents"
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            copy_file(agent_file, dest / ".claude" / "agents" / agent_file.name, args.dry_run)

    for doc in DOCS_TO_COPY:
        src_doc = source_repo / doc
        if src_doc.exists():
            copy_file(src_doc, dest / doc, args.dry_run)
        else:
            print(f"  skip   {src_doc} (not found)")

    feature_dir = source_repo / "docs" / "features" / args.app_slug
    if feature_dir.is_dir():
        copy_tree(feature_dir, dest / "docs" / "features" / args.app_slug, args.dry_run)
    else:
        print(f"  skip   {feature_dir} (no matching feature directory — nothing to bring over)")

    return dest


def git_init_and_commit(dest: Path, dry_run: bool) -> None:
    print(f"\nInitializing git repo at {dest}")
    if dry_run:
        print("  (skipped: --dry-run)")
        return
    # -b main: match organize-me/event-creator's default branch, since ci.yml/deploy.yml trigger
    # on pushes/PRs to "main" — git's own init default (often "master" on older git installs)
    # would silently mean CI never runs until someone notices and renames the branch by hand.
    subprocess.run(["git", "init", "-b", "main"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Scaffold hosted-app repo via /new-hosted-app skill"],
        cwd=dest,
        check=True,
    )


def gh_create_and_push(dest: Path, owner: str, slug: str, visibility: str, dry_run: bool) -> None:
    repo_spec = f"{owner}/{slug}"
    print(f"\nCreating {repo_spec} on GitHub ({visibility}) and pushing")
    if dry_run:
        print("  (skipped: --dry-run)")
        return
    subprocess.run(
        [
            "gh",
            "repo",
            "create",
            repo_spec,
            f"--{visibility}",
            "--source=.",
            "--remote=origin",
            "--push",
        ],
        cwd=dest,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("app_slug", help="kebab-case repo/service/schema name, e.g. doc-library")
    parser.add_argument("app_title", help="Human-readable app name, e.g. 'Doc Library'")
    parser.add_argument("--dest", type=Path, default=None, help="Destination directory (default: sibling of the source repo)")
    parser.add_argument("--github-owner", default=DEFAULT_GITHUB_OWNER)
    parser.add_argument("--gcp-project", default=DEFAULT_GCP_PROJECT_ID)
    parser.add_argument("--gcp-region", default=DEFAULT_GCP_REGION)
    parser.add_argument("--chrome-tag", default=None, help="Override the auto-detected latest chrome-v* tag")
    parser.add_argument("--visibility", choices=["public", "private"], default="public")
    parser.add_argument("--push", action="store_true", help="Also run `gh repo create ... --push` after scaffolding")
    parser.add_argument("--force", action="store_true", help="Reuse an existing, non-empty destination directory")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing/pushing anything")
    args = parser.parse_args()

    if not SLUG_RE.match(args.app_slug):
        fail(f"'{args.app_slug}' isn't kebab-case (expected e.g. 'doc-library')")

    source_repo = find_source_repo()
    if args.dest is None:
        args.dest = source_repo.parent / args.app_slug

    scaffold(args)
    git_init_and_commit(args.dest, args.dry_run)

    if args.push:
        gh_create_and_push(args.dest, args.github_owner, args.app_slug, args.visibility, args.dry_run)
    else:
        print(
            f"\nLocal repo ready at {args.dest}. Not pushed (pass --push once you've reviewed it) — "
            f"to push by hand: cd {args.dest} && gh repo create {args.github_owner}/{args.app_slug} "
            f"--{args.visibility} --source=. --remote=origin --push"
        )


if __name__ == "__main__":
    main()
