"""
Budget service — business logic for budget management and alerts.

Handles:
- Budget threshold checking (80% and 100% alerts)
- Budget overview generation
- Budget setup flow
- Budget deletion
- Copy budget to next month
"""

import logging
from datetime import datetime, date
from calendar import monthrange

from app.db.database import get_session
from app.db.repositories import (
    BudgetRepository,
    TransactionRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)

# Alert thresholds
THRESHOLD_WARNING = 0.80  # 80% — yellow warning
THRESHOLD_EXCEEDED = 1.00  # 100% — red alert


class BudgetService:
    """Business logic for budget management."""

    async def set_budget(
        self,
        platform_id: str,
        category: str,
        amount: float,
    ) -> dict:
        """Set a budget for a category in the current month."""
        month = datetime.now().strftime("%Y-%m")

        async with get_session() as session:
            user_repo = UserRepository(session)
            budget_repo = BudgetRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            budget = await budget_repo.set_budget(
                user_id=user.id,
                category=category,
                amount=amount,
                month=month,
            )

            return {
                "budget_id": budget.id,
                "category": budget.category,
                "amount": budget.amount,
                "month": budget.month,
            }

    async def get_overview(
        self,
        platform_id: str,
        month: str | None = None,
    ) -> dict:
        """
        Get budget overview with spending progress for each category.

        Returns dict with category → {budget, spent, remaining, percentage}.
        """
        if month is None:
            month = datetime.now().strftime("%Y-%m")

        async with get_session() as session:
            user_repo = UserRepository(session)
            budget_repo = BudgetRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            budgets = await budget_repo.get_all_budgets(user.id, month)
            summary = await txn_repo.get_summary(user.id, month)

            if not budgets:
                return {
                    "month": month,
                    "budgets": [],
                    "total_budget": 0,
                    "total_spent": summary["total"],
                }

            budget_items = []
            total_budget = 0.0

            for b in budgets:
                spent = summary["categories"].get(b.category, {}).get("total", 0.0)
                remaining = b.amount - spent
                percentage = (spent / b.amount * 100) if b.amount > 0 else 0

                budget_items.append({
                    "category": b.category,
                    "budget": b.amount,
                    "spent": spent,
                    "remaining": remaining,
                    "percentage": percentage,
                })
                total_budget += b.amount

            return {
                "month": month,
                "budgets": budget_items,
                "total_budget": total_budget,
                "total_spent": summary["total"],
            }

    async def check_budget_alert(
        self,
        platform_id: str,
        category: str,
    ) -> dict | None:
        """
        Check if a transaction pushes spending past budget thresholds.

        Returns alert info if threshold crossed, None otherwise.
        """
        month = datetime.now().strftime("%Y-%m")

        async with get_session() as session:
            user_repo = UserRepository(session)
            budget_repo = BudgetRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return None

            budget = await budget_repo.get_budget(user.id, category, month)
            if budget is None:
                return None  # No budget set for this category

            summary = await txn_repo.get_summary(user.id, month)
            spent = summary["categories"].get(category, {}).get("total", 0.0)
            percentage = spent / budget.amount if budget.amount > 0 else 0

            if percentage >= THRESHOLD_EXCEEDED:
                return {
                    "level": "exceeded",
                    "category": category,
                    "budget": budget.amount,
                    "spent": spent,
                    "percentage": percentage * 100,
                }
            elif percentage >= THRESHOLD_WARNING:
                return {
                    "level": "warning",
                    "category": category,
                    "budget": budget.amount,
                    "spent": spent,
                    "percentage": percentage * 100,
                }

            return None

    async def delete_budget(
        self,
        platform_id: str,
        category: str,
        month: str | None = None,
    ) -> dict:
        """
        Delete a budget for a category in the current (or specified) month.

        Returns {"success": True, "category": ...} or {"error": "..."}
        """
        if month is None:
            month = datetime.now().strftime("%Y-%m")

        async with get_session() as session:
            user_repo = UserRepository(session)
            budget_repo = BudgetRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            deleted = await budget_repo.delete_budget(user.id, category, month)
            if not deleted:
                return {"error": f"Budget untuk '{category}' tidak ditemukan di bulan {month}"}

            logger.info(f"Deleted budget for {platform_id}: {category} ({month})")
            return {"success": True, "category": category, "month": month}

    async def copy_to_next_month(
        self,
        platform_id: str,
    ) -> dict:
        """
        Copy all budgets from current month to next month.
        Skips categories that already have a budget next month.

        Returns {"copied": N, "next_month": "YYYY-MM"} or {"error": "..."}
        """
        now = datetime.now()
        current_month = now.strftime("%Y-%m")

        # Calculate next month
        if now.month == 12:
            next_month_date = date(now.year + 1, 1, 1)
        else:
            next_month_date = date(now.year, now.month + 1, 1)
        next_month = next_month_date.strftime("%Y-%m")

        async with get_session() as session:
            user_repo = UserRepository(session)
            budget_repo = BudgetRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            copied = await budget_repo.copy_budgets_to_month(
                user_id=user.id,
                from_month=current_month,
                to_month=next_month,
            )

            logger.info(
                f"Copied {copied} budget(s) from {current_month} to {next_month} "
                f"for user {platform_id}"
            )
            return {
                "copied": copied,
                "from_month": current_month,
                "next_month": next_month,
            }
