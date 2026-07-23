-- CI-only stand-in for the shared host schema: ha-dashboard has no QA/shared Supabase tier (see
-- organize-me's docs/adr/ha-dashboard-no-qa-environment.md), so unlike doc-library/event-creator's
-- CI, the throwaway Postgres service container in ci.yml/deploy.yml's smoke-test job has no
-- host.users table for 0002_grant_host_users_references.py's GRANT or tests/conftest.py's
-- create_host_user() to target. Column set/defaults mirror organize-me's real migrations exactly
-- (be144404ee27_create_users_table.py + 6e2b192a0f9a_add_nav_collapsed_groups_to_users.py) - keep
-- this file in sync if that table ever changes. Sourced identically from both workflows via
-- `psql "$DATABASE_URL" -f scripts/ci/bootstrap_host_users.sql` rather than duplicated inline.
CREATE SCHEMA IF NOT EXISTS host;
CREATE TABLE IF NOT EXISTS host.users (
    id UUID PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    name VARCHAR,
    phone_number VARCHAR,
    dark_mode BOOLEAN NOT NULL DEFAULT false,
    notification_sms BOOLEAN NOT NULL DEFAULT true,
    notification_email BOOLEAN NOT NULL DEFAULT true,
    onboarding_storage_done BOOLEAN NOT NULL DEFAULT false,
    onboarding_notifications_done BOOLEAN NOT NULL DEFAULT false,
    onboarding_first_upload_done BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hashed_password VARCHAR(1024) NOT NULL,
    is_active BOOLEAN NOT NULL,
    is_superuser BOOLEAN NOT NULL,
    is_verified BOOLEAN NOT NULL,
    nav_collapsed_groups JSON NOT NULL DEFAULT '{}'
);
