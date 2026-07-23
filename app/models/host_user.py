"""Read-only mapping onto the Host's `host.users` table (Slice 2, R7 gotcha pattern).

HA Dashboard owns no `User`/fastapi-users model of its own (see app.core.auth's docstring) - the
Host-issued JWT tells us *which* user id is making a request, nothing more. The empty-state page
needs the Host's `dark_mode` preference so the shared chrome renders in the user's actual theme
instead of defaulting to light.

`HostUser` is mapped onto `host.users` - the same Postgres database, a cross-schema query, no
network call - but is **select-only by convention and by construction**:

- It's mapped on the same `app.db.base.Base` as every other model here, NOT a separate metadata -
  a string-based `ForeignKey("host.users.id")` (any future ha_dashboard table needing one) only
  resolves against a table registered in the *same* `MetaData`. Safety from Alembic autogenerate
  ever managing this table instead comes from `migrations/env.py`'s `include_object` filter, which
  excludes the `host` schema outright.
- Only the columns this service actually reads are declared (`id`, `dark_mode`,
  `nav_collapsed_groups`) - deliberately omitting `email`, `hashed_password`, `is_active`, etc.,
  which live on the Host's real `User` model and are none of HA Dashboard's concern.
- Nothing in this codebase ever `db.add()`s, updates, or deletes a `HostUser` - callers must only
  ever `select()` it. A `before_flush` event listener below backs this up with a runtime guard
  (ported from doc-library's issue #9 follow-up, brought in from day one here) - convention/review
  alone don't stop a future slice from accidentally attaching a `HostUser` write to a session that
  also has legitimate writes on it, which would otherwise only surface as a confusing FK/permissions
  error (or worse, silently succeed) at flush time.
"""

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, Uuid, event
from sqlalchemy.orm import Mapped, Session, UOWTransaction, mapped_column

from app.db.base import Base


class HostUser(Base):
    """SELECT-ONLY. Never insert/update/delete through this class - see module docstring."""

    __tablename__ = "users"
    __table_args__ = {"schema": "host"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    nav_collapsed_groups: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)


@event.listens_for(Session, "before_flush")
def _reject_host_user_writes(
    session: Session, flush_context: UOWTransaction, instances: Any | None
) -> None:
    """Refuse to flush any insert/update/delete of a `HostUser` - see the module docstring.

    Registered on the sync `Session` class (not `AsyncSession`, which has none of its own ORM
    events) - `AsyncSession.flush()` delegates to an underlying sync `Session` internally, so this
    still fires for this app's actual async sessions; this is SQLAlchemy's documented way to hook
    ORM-level events for async sessions.
    """
    offenders = [
        obj for obj in (*session.new, *session.dirty, *session.deleted) if isinstance(obj, HostUser)
    ]
    if offenders:
        raise RuntimeError(
            "HostUser is select-only - refusing to flush an insert/update/delete "
            f"({len(offenders)} pending). See app.models.host_user's module docstring."
        )
