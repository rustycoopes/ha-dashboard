"""Grant ha_dashboard_app REFERENCES on host.users (Slice 2, R7 gotcha pattern)

Revision ID: 0002_grant_host_users_references
Revises: 0001_create_ha_dashboard_schema
Create Date: 2026-07-23

This slice introduces the first cross-schema FK-shaped read: `app/models/host_user.py`'s
`HostUser` mapping. Mirrors doc_library's own 0001 grant (see organize-me's
d4e5f6a7b8c9_schema_separation_host_event_creator.py for the pattern this narrow grant follows) -
`ha_dashboard_app` must never be able to SELECT host.users, only reference it from a FK. Deferred
from Slice 1's baseline migration deliberately (see that migration's own docstring) until a real
HostUser model existed to justify it.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_grant_host_users_references"
down_revision: str | None = "0001_create_ha_dashboard_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA host TO ha_dashboard_app")
    op.execute("GRANT REFERENCES ON host.users TO ha_dashboard_app")


def downgrade() -> None:
    op.execute("REVOKE REFERENCES ON host.users FROM ha_dashboard_app")
    op.execute("REVOKE USAGE ON SCHEMA host FROM ha_dashboard_app")
