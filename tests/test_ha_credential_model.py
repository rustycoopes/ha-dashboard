"""Model-level tests for `HACredential` (Slice 3): the atomic upsert never creates a second row
for the same user (including under real concurrent writes), and deleting a Host user cascades to
delete their credential row at the DB level.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ha_credential import HACredential, get_ha_credential, upsert_ha_credential
from tests.conftest import create_host_user


async def test_upsert_creates_a_row_on_first_save(db_session: AsyncSession) -> None:
    user_id = await create_host_user(db_session)

    await upsert_ha_credential(
        db_session,
        user_id,
        ha_host_url="https://one.example.com",
        encrypted_token="enc-1",
        tested_at=datetime.now(UTC),
    )
    await db_session.flush()

    credential = await get_ha_credential(db_session, user_id)
    assert credential is not None
    assert credential.ha_host_url == "https://one.example.com"
    assert credential.last_tested_at is not None


async def test_upsert_again_overwrites_the_same_row_never_creating_a_second(
    db_session: AsyncSession,
) -> None:
    user_id = await create_host_user(db_session)
    await upsert_ha_credential(
        db_session,
        user_id,
        ha_host_url="https://one.example.com",
        encrypted_token="enc-1",
        tested_at=datetime.now(UTC),
    )
    await db_session.flush()
    first = await get_ha_credential(db_session, user_id)
    assert first is not None
    first_id, first_updated_at = first.id, first.updated_at

    await upsert_ha_credential(
        db_session,
        user_id,
        ha_host_url="https://two.example.com",
        encrypted_token="enc-2",
        tested_at=datetime.now(UTC),
    )
    await db_session.flush()

    rows = (
        (await db_session.execute(select(HACredential).where(HACredential.user_id == user_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id == first_id
    assert rows[0].ha_host_url == "https://two.example.com"
    assert rows[0].updated_at != first_updated_at


async def test_concurrent_upsert_by_the_same_user_resolves_to_one_row() -> None:
    """Two genuinely concurrent saves (two independent connections/transactions, not the shared
    rolled-back `db_session` fixture which can't safely run two statements at once) resolve to
    exactly one row with no unique-constraint violation - the point of the atomic
    `INSERT ... ON CONFLICT DO UPDATE` over select-then-insert/update.
    """
    from app.core.config import get_settings
    from app.db.url import to_asyncpg_url
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        to_asyncpg_url(get_settings().database_url), connect_args={"statement_cache_size": 0}
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    try:
        async with session_maker() as setup_session:
            # create_host_user (tests/conftest.py) generates its own random id - insert this
            # test's own row directly instead so both concurrent upserts below target the same,
            # known user_id.
            await setup_session.execute(
                text(
                    "INSERT INTO host.users "
                    "(id, email, hashed_password, is_active, is_superuser, is_verified) "
                    "VALUES (:id, :email, 'not-a-real-hash', true, false, true)"
                ),
                {"id": user_id, "email": f"concurrent-{user_id.hex}@example.com"},
            )
            await setup_session.commit()

        async def _upsert(host_url: str) -> None:
            async with session_maker() as session:
                await upsert_ha_credential(
                    session,
                    user_id,
                    ha_host_url=host_url,
                    encrypted_token=f"enc-{host_url}",
                    tested_at=datetime.now(UTC),
                )
                await session.commit()

        await asyncio.gather(_upsert("https://a.example.com"), _upsert("https://b.example.com"))

        async with session_maker() as check_session:
            rows = (
                (
                    await check_session.execute(
                        select(HACredential).where(HACredential.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].ha_host_url in ("https://a.example.com", "https://b.example.com")
    finally:
        async with session_maker() as cleanup_session:
            await cleanup_session.execute(
                text("DELETE FROM host.users WHERE id = :id"), {"id": user_id}
            )
            await cleanup_session.commit()
        await engine.dispose()


async def test_deleting_a_host_user_cascades_to_delete_their_ha_credential_row(
    db_session: AsyncSession,
) -> None:
    user_id = await create_host_user(db_session)
    await upsert_ha_credential(
        db_session,
        user_id,
        ha_host_url="https://one.example.com",
        encrypted_token="enc-1",
        tested_at=datetime.now(UTC),
    )
    await db_session.flush()
    assert await get_ha_credential(db_session, user_id) is not None

    await db_session.execute(text("DELETE FROM host.users WHERE id = :id"), {"id": user_id})
    await db_session.flush()

    assert await get_ha_credential(db_session, user_id) is None
