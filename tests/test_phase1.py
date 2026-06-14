"""
Tests for new Phase 1 features:
  - Repository: get_by_date_range, delete, update, update_settings
  - Budget service: set_budget, get_overview, check_budget_alert
  - Transaction service: get_history, parse_only
"""

import pytest
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base, User, Transaction, Budget
from app.db.repositories import UserRepository, TransactionRepository, BudgetRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def user_and_repos(db_session):
    """Create a test user and return (user, user_repo, txn_repo, budget_repo)."""
    user_repo = UserRepository(db_session)
    txn_repo = TransactionRepository(db_session)
    budget_repo = BudgetRepository(db_session)

    user = await user_repo.get_or_create(
        platform_id="test_user_phase1",
        platform="telegram",
        name="Phase1 Tester",
    )
    await db_session.flush()

    return user, user_repo, txn_repo, budget_repo


# ── User Settings Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_settings_currency(db_session):
    """Test updating user currency."""
    repo = UserRepository(db_session)
    await repo.get_or_create(platform_id="settings_test", name="Settings User")
    await db_session.commit()

    user = await repo.update_settings("settings_test", currency="USD")
    await db_session.commit()

    assert user is not None
    assert user.currency == "USD"


@pytest.mark.asyncio
async def test_update_settings_timezone(db_session):
    """Test updating user timezone."""
    repo = UserRepository(db_session)
    await repo.get_or_create(platform_id="tz_test", name="TZ User")
    await db_session.commit()

    user = await repo.update_settings("tz_test", timezone="Asia/Makassar")
    await db_session.commit()

    assert user is not None
    assert user.timezone == "Asia/Makassar"


@pytest.mark.asyncio
async def test_update_settings_not_found(db_session):
    """Test updating settings for non-existent user returns None."""
    repo = UserRepository(db_session)
    result = await repo.update_settings("nonexistent", currency="USD")
    assert result is None


# ── Transaction Date Range Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_by_date_range(user_and_repos, db_session):
    """Test getting transactions within a date range."""
    user, _, txn_repo, _ = user_and_repos
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)

    # Create transactions on different dates
    await txn_repo.create(user_id=user.id, amount=10000, transaction_date=today, source="text")
    await txn_repo.create(user_id=user.id, amount=20000, transaction_date=yesterday, source="text")
    await txn_repo.create(user_id=user.id, amount=30000, transaction_date=last_week, source="text")
    await db_session.commit()

    # Query for today only
    results = await txn_repo.get_by_date_range(user.id, today, today)
    assert len(results) == 1
    assert results[0].amount == 10000

    # Query for yesterday to today
    results = await txn_repo.get_by_date_range(user.id, yesterday, today)
    assert len(results) == 2

    # Query for full range
    results = await txn_repo.get_by_date_range(user.id, last_week, today)
    assert len(results) == 3


# ── Transaction Delete Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_transaction(user_and_repos, db_session):
    """Test deleting a transaction."""
    user, _, txn_repo, _ = user_and_repos

    txn = await txn_repo.create(user_id=user.id, amount=5000, source="text")
    await db_session.commit()

    assert txn.id is not None

    # Delete successfully
    result = await txn_repo.delete(txn.id, user.id)
    await db_session.commit()
    assert result is True

    # Try to get deleted transaction
    found = await txn_repo.get_by_id(txn.id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_transaction_wrong_user(user_and_repos, db_session):
    """Test that deleting another user's transaction fails."""
    user, _, txn_repo, _ = user_and_repos

    txn = await txn_repo.create(user_id=user.id, amount=5000, source="text")
    await db_session.commit()

    # Try to delete with wrong user_id
    result = await txn_repo.delete(txn.id, user_id=99999)
    assert result is False


# ── Transaction Update Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_transaction(user_and_repos, db_session):
    """Test updating a transaction's fields."""
    user, _, txn_repo, _ = user_and_repos

    txn = await txn_repo.create(
        user_id=user.id, amount=5000,
        category="Lainnya", source="text"
    )
    await db_session.commit()

    updated = await txn_repo.update(
        txn.id, user.id,
        amount=7500,
        category="Makanan & Minuman",
    )
    await db_session.commit()

    assert updated is not None
    assert updated.amount == 7500
    assert updated.category == "Makanan & Minuman"


@pytest.mark.asyncio
async def test_update_transaction_wrong_user(user_and_repos, db_session):
    """Test that updating another user's transaction fails."""
    user, _, txn_repo, _ = user_and_repos

    txn = await txn_repo.create(user_id=user.id, amount=5000, source="text")
    await db_session.commit()

    result = await txn_repo.update(txn.id, user_id=99999, amount=9999)
    assert result is None


# ── Transaction get_by_id Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_by_id(user_and_repos, db_session):
    """Test getting a transaction by ID."""
    user, _, txn_repo, _ = user_and_repos

    txn = await txn_repo.create(user_id=user.id, amount=12345, source="text")
    await db_session.commit()

    found = await txn_repo.get_by_id(txn.id)
    assert found is not None
    assert found.amount == 12345

    not_found = await txn_repo.get_by_id(99999)
    assert not_found is None
