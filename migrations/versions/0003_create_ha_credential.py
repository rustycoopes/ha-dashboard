"""Create ha_dashboard.ha_credential

Revision ID: 0003_create_ha_credential
Revises: 0002_grant_host_users_references
Create Date: 2026-07-23

Slice 3: the feature's one owned table - one row per Host user (UNIQUE user_id), holding the HA
host URL (plaintext) and the Fernet-encrypted long-lived access token. See
docs/adr/ha-dashboard-credential-storage.md for the per-user-not-singleton and
host-URL-not-encrypted decisions. FK to host.users.id relies on the REFERENCES-only grant 0002
already gave ha_dashboard_app.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_create_ha_credential"
down_revision: str | None = "0002_grant_host_users_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ha_credential",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ha_host_url", sa.Text(), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        # clock_timestamp(), not now() - now()/CURRENT_TIMESTAMP is frozen to the enclosing
        # transaction's start time, not wall-clock time, which would make two writes inside one
        # transaction (e.g. this repo's savepoint-per-test isolation fixture) get an identical
        # updated_at. See app/models/ha_credential.py's matching column comment.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["host.users.id"], ondelete="cascade", name="fk_ha_credential_user_id"
        ),
        sa.UniqueConstraint("user_id", name="uq_ha_credential_user_id"),
        schema="ha_dashboard",
    )


def downgrade() -> None:
    op.drop_table("ha_credential", schema="ha_dashboard")
