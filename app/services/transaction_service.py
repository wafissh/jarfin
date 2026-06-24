"""
Transaction service — business logic layer.
Connects bot handlers → AI parser → database.
"""

import logging
from datetime import date, datetime, timedelta

from app.ai.base import ParsedTransaction
from app.ai.parser import TransactionParser
from app.db.database import get_session
from app.db.repositories import TransactionRepository, UserRepository

logger = logging.getLogger(__name__)

PAGE_SIZE = 10  # items per page for history pagination


class TransactionService:
    """Business logic for processing and storing transactions."""

    def __init__(self, parser: TransactionParser):
        self.parser = parser

    async def process_text_message(
        self,
        platform_id: str,
        text: str,
        platform: str = "telegram",
        user_name: str | None = None,
    ) -> dict:
        """
        Process a text message from a user.

        Flow: text → AI parse → save to DB → return result
        """
        # 1. Parse via AI
        parsed = await self.parser.parse_text(text)

        # 2. Save to database
        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_or_create(
                platform_id=platform_id,
                platform=platform,
                name=user_name,
            )

            txn = await txn_repo.create(
                user_id=user.id,
                amount=parsed.amount,
                type=parsed.type,
                category=parsed.category,
                merchant=parsed.merchant,
                description=parsed.description,
                transaction_date=parsed.transaction_date,
                source="text",
            )

            logger.info(
                f"Saved transaction #{txn.id}: {txn.amount} ({txn.type}) [{txn.category}] for user {user.platform_id}"
            )

            return {
                "transaction_id": txn.id,
                "amount": txn.amount,
                "type": txn.type,
                "category": txn.category,
                "merchant": txn.merchant,
                "description": txn.description,
                "date": txn.date.isoformat() if txn.date else None,
                "confidence": parsed.confidence,
            }

    async def process_photo_message(
        self,
        platform_id: str,
        ocr_text: str | None = None,
        image_bytes: bytes | None = None,
        image_url: str | None = None,
        platform: str = "telegram",
        user_name: str | None = None,
    ) -> list[dict]:
        """
        Process a photo message (receipt/nota).

        Flow: photo → direct AI parse (or OCR fallback) → save to DB → return results
        """
        # 1. Parse receipt via AI (try direct image parsing first if bytes are provided)
        parsed_list = []
        if image_bytes:
            try:
                parsed_list = await self.parser.parse_receipt_image(image_bytes)
            except NotImplementedError:
                if ocr_text:
                    parsed_list = await self.parser.parse_receipt(ocr_text)
        elif ocr_text:
            parsed_list = await self.parser.parse_receipt(ocr_text)

        if not parsed_list:
            return []

        # 2. Save all transactions to database
        results = []
        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_or_create(
                platform_id=platform_id,
                platform=platform,
                name=user_name,
            )

            for parsed in parsed_list:
                txn = await txn_repo.create(
                    user_id=user.id,
                    amount=parsed.amount,
                    type=parsed.type,
                    category=parsed.category,
                    merchant=parsed.merchant,
                    description=parsed.description,
                    transaction_date=parsed.transaction_date,
                    source="image",
                    image_url=image_url,
                )

                results.append({
                    "transaction_id": txn.id,
                    "amount": txn.amount,
                    "type": txn.type,
                    "category": txn.category,
                    "merchant": txn.merchant,
                    "description": txn.description,
                    "date": txn.date.isoformat() if txn.date else None,
                    "confidence": parsed.confidence,
                })

            logger.info(
                f"Saved {len(results)} transaction(s) from receipt for user {user.platform_id}"
            )

        return results

    async def get_summary(
        self,
        platform_id: str,
        month: str | None = None,
    ) -> dict:
        """Get spending summary for a user."""
        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            return await txn_repo.get_summary(user.id, month)

    async def get_history(
        self,
        platform_id: str,
        period: str = "recent",
        page: int = 0,
    ) -> dict:
        """
        Get transaction history for a user with pagination.

        period options:
          - 'recent' → last N transactions (paginated)
          - 'hari ini' → today
          - 'minggu ini' → this week
          - 'bulan ini' → this month
          - 'YYYY-MM' → specific month
        """
        today = date.today()
        offset = page * PAGE_SIZE

        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            total_count = 0
            if period == "recent":
                total_count = await txn_repo.count_by_user(user.id)
                transactions = await txn_repo.get_by_user(
                    user.id, limit=PAGE_SIZE, offset=offset
                )
            elif period == "hari ini":
                total_count = await txn_repo.count_by_date_range(user.id, today, today)
                transactions = await txn_repo.get_by_date_range(
                    user.id, today, today, limit=PAGE_SIZE, offset=offset
                )
            elif period == "minggu ini":
                start = today - timedelta(days=today.weekday())  # Monday
                total_count = await txn_repo.count_by_date_range(user.id, start, today)
                transactions = await txn_repo.get_by_date_range(
                    user.id, start, today, limit=PAGE_SIZE, offset=offset
                )
            elif period == "bulan ini":
                start = today.replace(day=1)
                total_count = await txn_repo.count_by_date_range(user.id, start, today)
                transactions = await txn_repo.get_by_date_range(
                    user.id, start, today, limit=PAGE_SIZE, offset=offset
                )
            else:
                # Try YYYY-MM format
                try:
                    year, mon = period.split("-")
                    start = date(int(year), int(mon), 1)
                    # Last day of month
                    if int(mon) == 12:
                        end = date(int(year) + 1, 1, 1) - timedelta(days=1)
                    else:
                        end = date(int(year), int(mon) + 1, 1) - timedelta(days=1)
                    total_count = await txn_repo.count_by_date_range(user.id, start, end)
                    transactions = await txn_repo.get_by_date_range(
                        user.id, start, end, limit=PAGE_SIZE, offset=offset
                    )
                except (ValueError, IndexError):
                    total_count = await txn_repo.count_by_user(user.id)
                    transactions = await txn_repo.get_by_user(
                        user.id, limit=PAGE_SIZE, offset=offset
                    )

            import math
            total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

            return {
                "period": period,
                "page": page,
                "total_pages": total_pages,
                "count": len(transactions),
                "total_count": total_count,
                "transactions": [
                    {
                        "id": t.id,
                        "amount": t.amount,
                        "type": t.type,
                        "category": t.category or "Lainnya",
                        "merchant": t.merchant,
                        "description": t.description,
                        "date": t.date.isoformat() if t.date else None,
                        "source": t.source,
                    }
                    for t in transactions
                ],
            }

    async def parse_only(self, text: str) -> dict:
        """
        Parse a text message WITHOUT saving to DB.
        Used for confirmation flow: parse → preview → user confirm → save.
        Returns only the first transaction (backward compatibility for single-txn flow).
        """
        results = await self.parse_only_multi(text)
        return results[0] if results else {
            "amount": 0, "type": "expense", "category": "Lainnya",
            "merchant": None, "description": text[:100],
            "date": date.today().isoformat(), "confidence": 0.0,
        }

    async def parse_only_multi(self, text: str) -> list[dict]:
        """
        Parse a text message WITHOUT saving to DB — returns ALL detected transactions.
        Used for multi-transaction confirmation flow.
        """
        parsed_list = await self.parser.parse_text(text)
        return [
            {
                "amount": parsed.amount,
                "type": parsed.type,
                "category": parsed.category,
                "merchant": parsed.merchant,
                "description": parsed.description,
                "date": parsed.transaction_date.isoformat() if parsed.transaction_date else date.today().isoformat(),
                "confidence": parsed.confidence,
            }
            for parsed in parsed_list
        ]

    async def save_parsed(
        self,
        platform_id: str,
        parsed_data: dict,
        source: str = "text",
        platform: str = "telegram",
        user_name: str | None = None,
    ) -> dict:
        """Save a previously parsed transaction to DB after user confirmation."""
        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_or_create(
                platform_id=platform_id,
                platform=platform,
                name=user_name,
            )

            txn_date = None
            if parsed_data.get("date"):
                try:
                    txn_date = datetime.strptime(parsed_data["date"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    txn_date = date.today()

            txn = await txn_repo.create(
                user_id=user.id,
                amount=parsed_data["amount"],
                type=parsed_data.get("type", "expense"),
                category=parsed_data.get("category"),
                merchant=parsed_data.get("merchant"),
                description=parsed_data.get("description"),
                transaction_date=txn_date or date.today(),
                source=source,
            )

            logger.info(
                f"Confirmed & saved transaction #{txn.id}: {txn.amount} ({txn.type}) [{txn.category}]"
            )

            return {
                "transaction_id": txn.id,
                "amount": txn.amount,
                "type": txn.type,
                "category": txn.category,
                "merchant": txn.merchant,
                "description": txn.description,
                "date": txn.date.isoformat() if txn.date else None,
            }

    async def delete_transaction(
        self,
        platform_id: str,
        transaction_id: int,
    ) -> dict:
        """
        Delete a transaction by ID for a given user.

        Returns {"success": True} or {"error": "..."}
        """
        async with get_session() as session:
            user_repo = UserRepository(session)
            txn_repo = TransactionRepository(session)

            user = await user_repo.get_by_platform_id(platform_id)
            if user is None:
                return {"error": "User not found"}

            deleted = await txn_repo.delete(transaction_id, user.id)
            if not deleted:
                return {"error": "Transaction not found or not owned by user"}

            logger.info(
                f"Deleted transaction #{transaction_id} for user {platform_id}"
            )
            return {"success": True, "transaction_id": transaction_id}
