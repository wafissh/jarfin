"""
Repository pattern for database CRUD operations.
Each repository handles one model/table.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Transaction, Budget, RecurringTransaction


# ── User Repository ─────────────────────────────────────────────────────────

class UserRepository:
    """CRUD operations for the users table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(
        self,
        platform_id: str,
        platform: str = "telegram",
        name: str | None = None,
    ) -> User:
        """Get existing user or create a new one."""
        user = await self.get_by_platform_id(platform_id)
        if user is None:
            user = User(
                platform_id=platform_id,
                platform=platform,
                name=name,
            )
            self.session.add(user)
            await self.session.flush()
        return user

    async def get_by_platform_id(self, platform_id: str) -> User | None:
        """Find a user by their platform-specific ID."""
        stmt = select(User).where(User.platform_id == platform_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        """Find a user by internal ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_name(self, platform_id: str, name: str) -> User | None:
        """Update user's display name."""
        user = await self.get_by_platform_id(platform_id)
        if user:
            user.name = name
            await self.session.flush()
        return user

    async def update_settings(
        self,
        platform_id: str,
        currency: str | None = None,
        timezone: str | None = None,
    ) -> User | None:
        """Update user's currency and/or timezone settings."""
        user = await self.get_by_platform_id(platform_id)
        if user is None:
            return None
        if currency is not None:
            user.currency = currency
        if timezone is not None:
            user.timezone = timezone
        await self.session.flush()
        return user


# ── Transaction Repository ──────────────────────────────────────────────────

class TransactionRepository:
    """CRUD operations for the transactions table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        amount: float,
        type: str = "expense",
        category: str | None = None,
        merchant: str | None = None,
        description: str | None = None,
        transaction_date: date | None = None,
        source: str = "text",
        image_url: str | None = None,
    ) -> Transaction:
        """Create a new transaction."""
        txn = Transaction(
            user_id=user_id,
            amount=amount,
            type=type,
            category=category,
            merchant=merchant,
            description=description,
            date=transaction_date or date.today(),
            source=source,
            image_url=image_url,
        )
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get recent transactions for a user, newest first."""
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        """Count all transactions for a user."""
        stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Get a single transaction by ID."""
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get transactions within a date range, newest first."""
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> int:
        """Count transactions within a date range."""
        stmt = select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def delete(self, transaction_id: int, user_id: int) -> bool:
        """Delete a transaction. Returns True if deleted, False if not found."""
        txn = await self.get_by_id(transaction_id)
        if txn is None or txn.user_id != user_id:
            return False
        await self.session.delete(txn)
        await self.session.flush()
        return True

    async def update(
        self,
        transaction_id: int,
        user_id: int,
        **kwargs,
    ) -> Transaction | None:
        """Update a transaction's fields. Only updates provided kwargs."""
        txn = await self.get_by_id(transaction_id)
        if txn is None or txn.user_id != user_id:
            return None
        for key, value in kwargs.items():
            if hasattr(txn, key) and value is not None:
                setattr(txn, key, value)
        await self.session.flush()
        return txn

    async def get_summary(
        self,
        user_id: int,
        month: str | None = None,
    ) -> dict:
        """
        Get spending and income summary for a user.
        month format: 'YYYY-MM'. If None, returns current month.
        """
        if month is None:
            month = datetime.now().strftime("%Y-%m")

        year, mon = month.split("-")

        # Get expenses grouped by category
        stmt_expenses = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                func.strftime("%Y", Transaction.date) == year,
                func.strftime("%m", Transaction.date) == mon,
            )
            .group_by(Transaction.category)
        )
        result_expenses = await self.session.execute(stmt_expenses)
        rows_expenses = result_expenses.all()

        categories = {}
        total_expenses = 0.0
        for row in rows_expenses:
            cat_name = row.category or "Lainnya"
            categories[cat_name] = {
                "total": row.total,
                "count": row.count,
            }
            total_expenses += row.total

        # Get income grouped by category
        stmt_income_cats = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "income",
                func.strftime("%Y", Transaction.date) == year,
                func.strftime("%m", Transaction.date) == mon,
            )
            .group_by(Transaction.category)
        )
        result_income_cats = await self.session.execute(stmt_income_cats)
        rows_income = result_income_cats.all()

        income_categories = {}
        total_income = 0.0
        for row in rows_income:
            cat_name = row.category or "Lainnya"
            income_categories[cat_name] = {
                "total": row.total,
                "count": row.count,
            }
            total_income += row.total

        return {
            "month": month,
            "total": total_expenses,
            "total_expenses": total_expenses,
            "total_income": total_income,
            "categories": categories,
            "income_categories": income_categories,
        }


# ── Budget Repository ───────────────────────────────────────────────────────

class BudgetRepository:
    """CRUD operations for the budgets table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_budget(
        self,
        user_id: int,
        category: str,
        amount: float,
        month: str,
    ) -> Budget:
        """Set or update a budget for a category in a specific month."""
        stmt = select(Budget).where(
            Budget.user_id == user_id,
            Budget.category == category,
            Budget.month == month,
        )
        result = await self.session.execute(stmt)
        budget = result.scalar_one_or_none()

        if budget:
            budget.amount = amount
        else:
            budget = Budget(
                user_id=user_id,
                category=category,
                amount=amount,
                month=month,
            )
            self.session.add(budget)

        await self.session.flush()
        return budget

    async def get_budget(
        self,
        user_id: int,
        category: str,
        month: str,
    ) -> Budget | None:
        """Get budget for a specific category and month."""
        stmt = select(Budget).where(
            Budget.user_id == user_id,
            Budget.category == category,
            Budget.month == month,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_budgets(
        self,
        user_id: int,
        month: str,
    ) -> list[Budget]:
        """Get all budgets for a user in a specific month."""
        stmt = (
            select(Budget)
            .where(Budget.user_id == user_id, Budget.month == month)
            .order_by(Budget.category)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_budget(
        self,
        user_id: int,
        category: str,
        month: str,
    ) -> bool:
        """Delete a budget for a specific category and month. Returns True if deleted."""
        stmt = sa_delete(Budget).where(
            Budget.user_id == user_id,
            Budget.category == category,
            Budget.month == month,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def copy_budgets_to_month(
        self,
        user_id: int,
        from_month: str,
        to_month: str,
    ) -> int:
        """
        Copy all budgets from one month to another.
        Skips categories that already have a budget in the target month.
        Returns the number of budgets copied.
        """
        source_budgets = await self.get_all_budgets(user_id, from_month)
        if not source_budgets:
            return 0

        copied = 0
        for b in source_budgets:
            existing = await self.get_budget(user_id, b.category, to_month)
            if existing is None:
                new_budget = Budget(
                    user_id=user_id,
                    category=b.category,
                    amount=b.amount,
                    month=to_month,
                )
                self.session.add(new_budget)
                copied += 1

        if copied > 0:
            await self.session.flush()
        return copied


# ── Recurring Transaction Repository ───────────────────────────────────────

class RecurringTransactionRepository:
    """CRUD operations for the recurring_transactions table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        amount: float,
        type: str = "expense",
        category: str | None = None,
        merchant: str | None = None,
        description: str | None = None,
        frequency: str = "monthly",
        day_of_month: int | None = None,
        next_run_date: date | None = None,
    ) -> RecurringTransaction:
        """Create a new recurring transaction template."""
        rec = RecurringTransaction(
            user_id=user_id,
            amount=amount,
            type=type,
            category=category,
            merchant=merchant,
            description=description,
            frequency=frequency,
            day_of_month=day_of_month,
            next_run_date=next_run_date or date.today(),
            is_active=True,
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def get_by_user(self, user_id: int) -> list[RecurringTransaction]:
        """Get all active recurring transactions for a user."""
        stmt = (
            select(RecurringTransaction)
            .where(
                RecurringTransaction.user_id == user_id,
                RecurringTransaction.is_active == True,  # noqa: E712
            )
            .order_by(RecurringTransaction.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, rec_id: int) -> RecurringTransaction | None:
        """Get a single recurring transaction by ID."""
        stmt = select(RecurringTransaction).where(RecurringTransaction.id == rec_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_due_today(self) -> list[RecurringTransaction]:
        """Get all active recurring transactions due today or overdue."""
        today = date.today()
        stmt = (
            select(RecurringTransaction)
            .where(
                RecurringTransaction.is_active == True,  # noqa: E712
                RecurringTransaction.next_run_date <= today,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_next_run(self, rec_id: int, next_run_date: date) -> RecurringTransaction | None:
        """Update the next_run_date after execution."""
        rec = await self.get_by_id(rec_id)
        if rec is None:
            return None
        rec.next_run_date = next_run_date
        await self.session.flush()
        return rec

    async def deactivate(self, rec_id: int, user_id: int) -> bool:
        """Soft-delete a recurring transaction (set is_active=False)."""
        rec = await self.get_by_id(rec_id)
        if rec is None or rec.user_id != user_id:
            return False
        rec.is_active = False
        await self.session.flush()
        return True
