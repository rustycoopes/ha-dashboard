"""Create the ha_dashboard schema and its app role

Revision ID: 0001_create_ha_dashboard_schema
Revises:
Create Date: 2026-07-23

Baseline of ha-dashboard's own independent Alembic history (Slice 1,
version_table_schema="ha_dashboard" in migrations/env.py). Like doc_library, ha_dashboard never
existed in any prior monolith - this is the first real DDL for this app. No tables yet, and no
grant on host.users either: unlike doc_library's own baseline, no HostUser cross-schema model
exists yet in this slice, and the throwaway Postgres this migration also runs against in CI (see
.github/workflows/deploy.yml's smoke-test job) has no host schema at all to reference. Add the
REFERENCES-only grant on host.users (mirroring doc_library's 0001) in whichever future slice
actually introduces that FK.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_ha_dashboard_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMAA IF NOT EXISTS ha_dashboard")  # TEMP: deliberate typo, verifying CI gate
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ha_dashboard_app') THEN
                CREATE ROLE ha_dashboard_app NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA ha_dashboard TO ha_dashboard_app")
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA ha_dashboard TO ha_dashboard_app")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA ha_dashboard TO ha_dashboard_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA ha_dashboard GRANT ALL ON TABLES TO ha_dashboard_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA ha_dashboard GRANT ALL ON SEQUENCES TO ha_dashboard_app"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA ha_dashboard "
        "REVOKE ALL ON SEQUENCES FROM ha_dashboard_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA ha_dashboard REVOKE ALL ON TABLES FROM ha_dashboard_app"
    )
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA ha_dashboard FROM ha_dashboard_app")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA ha_dashboard FROM ha_dashboard_app")
    op.execute("REVOKE USAGE ON SCHEMA ha_dashboard FROM ha_dashboard_app")
    op.execute("DROP ROLE IF EXISTS ha_dashboard_app")
    op.execute("DROP SCHEMA IF EXISTS ha_dashboard")
