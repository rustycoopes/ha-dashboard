"""A user's stored Home Assistant connection (Slice 3 - the feature's one owned table).

One row per Host user (``user_id`` is ``UNIQUE``) - see
docs/adr/ha-dashboard-credential-storage.md for why per-user, not a global singleton, and why
``ha_host_url`` specifically isn't encrypted. ``encrypted_token`` holds Fernet ciphertext produced
by ``app.core.security.CredentialCipher`` - this module never encrypts/decrypts itself, callers
do that before/after persistence.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HACredential(Base):
    __tablename__ = "ha_credential"
    __table_args__ = {"schema": "ha_dashboard"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("host.users.id", ondelete="cascade"), nullable=False, unique=True
    )
    ha_host_url: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # No `onupdate=func.now()` here - the only write path (upsert_ha_credential below) is a raw
    # Core `INSERT ... ON CONFLICT DO UPDATE` statement, which never goes through ORM flush/update
    # and so would never trigger it. `upsert_ha_credential`'s own `set_={"updated_at": func.now()}`
    # is what actually bumps this column - an `onupdate` here would be dead config that misleads a
    # future contributor into assuming any ORM-level touch updates it.
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def get_ha_credential(db: AsyncSession, user_id: uuid.UUID) -> HACredential | None:
    """The user's own credential row, or ``None`` if they haven't configured one yet.

    Every read resolves ``user_id`` from the verified JWT (``current_user_id``), never from the
    request body - a row that doesn't belong to the requesting user is invisible to them, same
    404-not-403 convention ``doc-library`` uses.
    """
    result = await db.execute(select(HACredential).where(HACredential.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_ha_credential(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    ha_host_url: str,
    encrypted_token: str,
    tested_at: datetime,
) -> None:
    """Atomically create-or-update the user's single credential row.

    An ``INSERT ... ON CONFLICT (user_id) DO UPDATE`` rather than select-then-insert/update, so
    two concurrent saves by the same user (e.g. from two open tabs) can't race each other into a
    duplicate-row unique-constraint violation - matches ``doc-library``'s
    ``user_preference.set_view_mode`` pattern. ``last_tested_at`` is always set here: both the
    Test Connection and Save routes only call this after their own successful full HA fetch.

    Does not commit - the calling route handler owns the transaction boundary.
    """
    stmt = pg_insert(HACredential).values(
        id=uuid.uuid4(),
        user_id=user_id,
        ha_host_url=ha_host_url,
        encrypted_token=encrypted_token,
        last_tested_at=tested_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[HACredential.user_id],
        set_={
            "ha_host_url": ha_host_url,
            "encrypted_token": encrypted_token,
            "last_tested_at": tested_at,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    # This is a raw Core statement, not an ORM-tracked update - it never touches the session's
    # identity map, so a HACredential instance already loaded earlier on this same session (e.g.
    # a prior get_ha_credential() call) would otherwise keep serving its stale, pre-upsert column
    # values on the next read instead of re-querying. Expiring here means any such instance
    # re-fetches from the DB on next attribute access, same as after an ORM-tracked write.
    db.expire_all()
