"""Read-only lookup of a user's Host-owned profile fields (Slice 2, R7 gotcha pattern).

Thin wrapper around a `select()` against `app.models.host_user.HostUser` - see that module's
docstring for why this must stay select-only.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host_user import HostUser


async def get_host_user(db: AsyncSession, user_id: uuid.UUID) -> HostUser | None:
    """The Host's `host.users` row for `user_id`, or ``None`` if it doesn't exist.

    In practice this should always find a row for any `user_id` extracted from a valid Host JWT
    (the JWT is only ever issued for a real Host user) - ``None`` is handled defensively rather
    than assumed unreachable, the same caution `app.core.auth.current_user_id_optional` takes with
    the token's own claims.
    """
    result = await db.execute(select(HostUser).where(HostUser.id == user_id))
    return result.scalar_one_or_none()
