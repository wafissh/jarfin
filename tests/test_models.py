"""
Tests for database models and repositories.
"""

import pytest
from datetime import date

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


# ── User Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user(db_session):
    """Test creating a new user."""
    repo = UserRepository(db_session)
    user = await repo.get_or_create(
        platform_id="12345",
        platform="telegram",
        name="Test User",
    )
    await db_session.commit()

    assert user.id is not None
    assert user.platform_id == "12345"
    assert user.platform == "telegram"
    assert user.name == "Test User"
    assert user.currency == "IDR"
    assert user.timezone == "Asia/Jakarta"
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_get_or_create_existing_user(db_session):
    """Test that get_or_create returns existing user."""
    repo = UserRepository(db_session)

    user1 = await repo.get_or_create(platform_id="12345", name="User 1")
    user2 = await repo.get_or_create(platform_id="12345", name="User 2")
    await db_session.commit()

    assert user1.id == user2.id  # Same user returned


@pytest.mark.asyncio
async def test_get_user_by_platform_id(db_session):
    """Test finding a user by platform ID."""
    repo = UserRepository(db_session)
    await repo.get_or_create(platform_id="99999", name="Finder")
    await db_session.commit()

    found = await repo.get_by_platform_id("99999")
    assert found is not None
    assert found.name == "Finder"

    not_found = await repo.get_by_platform_id("00000")
    assert not_found is None


# ── Transaction Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_transaction(db_session):
    """Test creating a transaction."""
    user_repo = UserRepository(db_session)
    txn_repo = TransactionRepository(db_session)

    user = await user_repo.get_or_create(platform_id="111", name="Spender")
    await db_session.flush()

    txn = await txn_repo.create(
        user_id=user.id,
        amount=25000,
        type="expense",
        category="Makanan & Minuman",
        merchant="Warteg",
        description="Makan siang",
        transaction_date=date.today(),
        source="text",
    )
    
    txn_income = await txn_repo.create(
        user_id=user.id,
        amount=5000000,
        type="income",
        category="Lainnya",
        description="Gaji bulanan",
        transaction_date=date.today(),
        source="text",
    )
    await db_session.commit()

    assert txn.id is not None
    assert txn.amount == 25000
    assert txn.type == "expense"
    assert txn.category == "Makanan & Minuman"
    assert txn.merchant == "Warteg"
    assert txn.source == "text"
    
    assert txn_income.id is not None
    assert txn_income.amount == 5000000
    assert txn_income.type == "income"


@pytest.mark.asyncio
async def test_get_transactions_by_user(db_session):
    """Test getting transactions for a user."""
    user_repo = UserRepository(db_session)
    txn_repo = TransactionRepository(db_session)

    user = await user_repo.get_or_create(platform_id="222", name="Multi")
    await db_session.flush()

    await txn_repo.create(user_id=user.id, amount=10000, type="expense", source="text")
    await txn_repo.create(user_id=user.id, amount=20000, type="expense", source="text")
    await txn_repo.create(user_id=user.id, amount=30000, type="income", source="image")
    await db_session.commit()

    transactions = await txn_repo.get_by_user(user.id)
    assert len(transactions) == 3


@pytest.mark.asyncio
async def test_transaction_summary(db_session):
    """Test monthly spending and income summary."""
    user_repo = UserRepository(db_session)
    txn_repo = TransactionRepository(db_session)

    user = await user_repo.get_or_create(platform_id="333", name="Summary")
    await db_session.flush()

    today = date.today()
    await txn_repo.create(
        user_id=user.id, amount=25000, type="expense", category="Makanan & Minuman",
        transaction_date=today, source="text"
    )
    await txn_repo.create(
        user_id=user.id, amount=15000, type="expense", category="Transportasi",
        transaction_date=today, source="text"
    )
    await txn_repo.create(
        user_id=user.id, amount=30000, type="expense", category="Makanan & Minuman",
        transaction_date=today, source="text"
    )
    await txn_repo.create(
        user_id=user.id, amount=5000000, type="income", category="Lainnya",
        transaction_date=today, source="text"
    )
    await db_session.commit()

    month = today.strftime("%Y-%m")
    summary = await txn_repo.get_summary(user.id, month)

    assert summary["total_expenses"] == 70000
    assert summary["total_income"] == 5000000
    assert "Makanan & Minuman" in summary["categories"]
    assert summary["categories"]["Makanan & Minuman"]["total"] == 55000
    assert summary["categories"]["Makanan & Minuman"]["count"] == 2
    assert summary["categories"]["Transportasi"]["total"] == 15000


# ── Budget Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_and_get_budget(db_session):
    """Test setting and getting a budget."""
    user_repo = UserRepository(db_session)
    budget_repo = BudgetRepository(db_session)

    user = await user_repo.get_or_create(platform_id="444", name="Budgeter")
    await db_session.flush()

    budget = await budget_repo.set_budget(
        user_id=user.id,
        category="Makanan & Minuman",
        amount=500000,
        month="2026-06",
    )
    await db_session.commit()

    assert budget.id is not None
    assert budget.amount == 500000

    # Update budget
    updated = await budget_repo.set_budget(
        user_id=user.id,
        category="Makanan & Minuman",
        amount=600000,
        month="2026-06",
    )
    await db_session.commit()

    assert updated.id == budget.id  # Same record updated
    assert updated.amount == 600000


@pytest.mark.asyncio
async def test_get_all_budgets(db_session):
    """Test getting all budgets for a month."""
    user_repo = UserRepository(db_session)
    budget_repo = BudgetRepository(db_session)

    user = await user_repo.get_or_create(platform_id="555", name="Multi Budget")
    await db_session.flush()

    await budget_repo.set_budget(user.id, "Makanan & Minuman", 500000, "2026-06")
    await budget_repo.set_budget(user.id, "Transportasi", 300000, "2026-06")
    await budget_repo.set_budget(user.id, "Hiburan", 200000, "2026-06")
    await db_session.commit()

    budgets = await budget_repo.get_all_budgets(user.id, "2026-06")
    assert len(budgets) == 3
