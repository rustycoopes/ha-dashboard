"""Runtime write-guard on the read-only `HostUser` mapping (ported from doc-library's issue #9
follow-up, brought in from day one here rather than as a later fix)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host_user import HostUser
from tests.conftest import create_host_user


async def test_adding_a_host_user_raises_on_flush(db_session: AsyncSession) -> None:
    db_session.add(HostUser(id=uuid.uuid4(), dark_mode=False, nav_collapsed_groups={}))

    with pytest.raises(RuntimeError, match="select-only"):
        await db_session.flush()


async def test_mutating_a_selected_host_user_raises_on_flush(db_session: AsyncSession) -> None:
    user_id = await create_host_user(db_session)
    host_user = await db_session.get(HostUser, user_id)
    assert host_user is not None

    host_user.dark_mode = not host_user.dark_mode

    with pytest.raises(RuntimeError, match="select-only"):
        await db_session.flush()


async def test_deleting_a_host_user_via_the_orm_raises_on_flush(db_session: AsyncSession) -> None:
    user_id = await create_host_user(db_session)
    host_user = await db_session.get(HostUser, user_id)
    assert host_user is not None

    await db_session.delete(host_user)

    with pytest.raises(RuntimeError, match="select-only"):
        await db_session.flush()


async def test_raw_sql_insert_used_by_test_fixtures_is_unaffected(db_session: AsyncSession) -> None:
    # create_host_user() (used by every other test in this suite) inserts via raw SQL, not the
    # ORM - the guard must not interfere with that path.
    user_id = await create_host_user(db_session)

    assert await db_session.get(HostUser, user_id) is not None
