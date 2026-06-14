"""
Recurring Transaction Service — business logic for scheduled transactions.

Handles:
- Creating recurring transaction templates
- Listing recurring transactions per user
- Executing due recurring transactions (inserting actual Transaction records)
- Deleting recurring transactions
"""

import logging
from datetime import date, timedelta

from app.db.database import get_session
from app.db.repositories import (
    RecurringTransactionRepository,
    TransactionRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


def _compute_next_run(current: date, frequency: str, day_of_month: int | None) -> date:
    """
    Compute the next run date based on frequency.

    - daily   → tomorrow
    - weekly  → same weekday next week
    - monthly → same day next month (capped to last day of month)
    """
    if frequency == "daily":
        return current + timedelta(days=1)

    elif frequency == "weekly":
        return current + timedelta(weeks=1)

    else:  # monthly
        month = current.month + 1
        year = current.year
        if month > 12:
            month = 1
            year += 1

        day = day_of_month or current.day
        # Cap to last day of target month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        day = min(day, last_day)
        return date(year, month, day)


class RecurringService:
    """Business logic for recurring (scheduled) transactions."""

    async def create_recurring(
        self,
        platform_id: str,
        amount: float,
        description: str,
        category: str,
        type: str = "expense",
        merchant: str | None = None,
        frequency: str = "monthly",
        day_of_month: int | None = None,
    ) -> dict:
        """
        Create a new recurring transaction template.

        day_of_month: day of month to run (1-28) for monthly frequency.
        If None, uses today's day.
        """
        today = date.today()

        # First run: if day_of_month is today or in the past this month,
        # schedule next run for next occurrence.
        if frequency == "monthly":
            dom = day_of_month or today.day
            if today.day >= dom:
                # schedule next month
                next_run = _compute_next_run(
                    date(today.year, today.month, dom), "monthly", dom
                )
            else:
                import calendar
                last_day = calendar.monthrange(today.year, today.month)[1]
                next_run = date(today.year, today.month, min(dom, last_day))
        elif frequency == "weekly":
            next_run = today + timedelta(weeks=1)
        else:  # daily
            next_run = today + timedelta(days=1)

        async with get_session() as session:
            user_repo = UserRepository(session)
            rec_repo = RecurringTransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found. Kirim /start dulu."}

            rec = await rec_repo.create(
                user_id=user.id,
                amount=amount,
                type=type,
                category=category,
                merchant=merchant,
                description=description,
                frequency=frequency,
                day_of_month=day_of_month or today.day,
                next_run_date=next_run,
            )

            logger.info(
                f"Created recurring #{rec.id}: {amount} [{category}] "
                f"{frequency}, next={next_run} for user {platform_id}"
            )

            freq_labels = {"daily": "Harian", "weekly": "Mingguan", "monthly": "Bulanan"}
            return {
                "recurring_id": rec.id,
                "amount": rec.amount,
                "category": rec.category,
                "description": rec.description,
                "frequency": freq_labels.get(rec.frequency, rec.frequency),
                "next_run_date": rec.next_run_date.isoformat() if rec.next_run_date else None,
            }

    async def list_recurring(self, platform_id: str) -> dict:
        """List all active recurring transactions for a user."""
        async with get_session() as session:
            user_repo = UserRepository(session)
            rec_repo = RecurringTransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            recs = await rec_repo.get_by_user(user.id)

            freq_labels = {"daily": "Harian", "weekly": "Mingguan", "monthly": "Bulanan"}
            return {
                "count": len(recs),
                "items": [
                    {
                        "id": r.id,
                        "amount": r.amount,
                        "type": r.type,
                        "category": r.category or "Lainnya",
                        "merchant": r.merchant,
                        "description": r.description,
                        "frequency": freq_labels.get(r.frequency, r.frequency),
                        "next_run_date": r.next_run_date.isoformat() if r.next_run_date else None,
                    }
                    for r in recs
                ],
            }

    async def delete_recurring(self, platform_id: str, rec_id: int) -> dict:
        """Deactivate (soft-delete) a recurring transaction."""
        async with get_session() as session:
            user_repo = UserRepository(session)
            rec_repo = RecurringTransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            deleted = await rec_repo.deactivate(rec_id, user.id)
            if not deleted:
                return {"error": "Transaksi rutin tidak ditemukan"}

            logger.info(f"Deactivated recurring #{rec_id} for user {platform_id}")
            return {"success": True, "recurring_id": rec_id}

    async def execute_now(self, platform_id: str, rec_id: int) -> dict:
        """
        Manually execute a recurring transaction immediately.
        Creates an actual Transaction record and updates next_run_date.
        """
        async with get_session() as session:
            user_repo = UserRepository(session)
            rec_repo = RecurringTransactionRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            rec = await rec_repo.get_by_id(rec_id)
            if rec is None or rec.user_id != user.id:
                return {"error": "Transaksi rutin tidak ditemukan"}

            # Create the actual transaction
            txn = await txn_repo.create(
                user_id=user.id,
                amount=rec.amount,
                type=rec.type,
                category=rec.category,
                merchant=rec.merchant,
                description=rec.description,
                transaction_date=date.today(),
                source="recurring",
            )

            # Update next run date
            next_run = _compute_next_run(date.today(), rec.frequency, rec.day_of_month)
            await rec_repo.update_next_run(rec_id, next_run)

            logger.info(
                f"Executed recurring #{rec_id} → transaction #{txn.id} "
                f"for user {platform_id}. Next run: {next_run}"
            )

            return {
                "success": True,
                "transaction_id": txn.id,
                "amount": txn.amount,
                "category": txn.category,
                "next_run_date": next_run.isoformat(),
            }

    async def run_due_transactions(self) -> int:
        """
        Background job: execute all recurring transactions due today.
        Returns number of transactions executed.

        This should be called periodically (e.g., daily at midnight).
        """
        executed = 0
        async with get_session() as session:
            rec_repo = RecurringTransactionRepository(session)
            txn_repo = TransactionRepository(session)

            due_recs = await rec_repo.get_due_today()
            logger.info(f"Found {len(due_recs)} recurring transaction(s) due today")

            for rec in due_recs:
                try:
                    txn = await txn_repo.create(
                        user_id=rec.user_id,
                        amount=rec.amount,
                        type=rec.type,
                        category=rec.category,
                        merchant=rec.merchant,
                        description=rec.description,
                        transaction_date=date.today(),
                        source="recurring",
                    )

                    next_run = _compute_next_run(date.today(), rec.frequency, rec.day_of_month)
                    await rec_repo.update_next_run(rec.id, next_run)

                    logger.info(
                        f"Auto-executed recurring #{rec.id} → txn #{txn.id}. "
                        f"Next: {next_run}"
                    )
                    executed += 1
                except Exception as e:
                    logger.error(f"Failed to execute recurring #{rec.id}: {e}")

        return executed
