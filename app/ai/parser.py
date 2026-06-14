"""
Transaction parser — uses an AIProvider via dependency injection.

Usage:
    from app.ai.gemini_provider import GeminiProvider
    from app.ai.parser import TransactionParser

    parser = TransactionParser(provider=GeminiProvider())
    result = await parser.parse("Makan siang 35000")

To switch to a different AI model:
    from app.ai.some_other_provider import OtherProvider
    parser = TransactionParser(provider=OtherProvider())

No other code changes needed.
"""

import logging
from app.ai.base import AIProvider, ParsedTransaction

logger = logging.getLogger(__name__)


class TransactionParser:
    """
    High-level transaction parser.
    Delegates to an AIProvider for the actual parsing.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def parse_text(self, text: str) -> ParsedTransaction:
        """
        Parse a user's text message into a structured transaction.

        Args:
            text: Natural language input, e.g., "Kopi Starbucks 55000"

        Returns:
            ParsedTransaction with extracted fields.
        """
        logger.info(f"Parsing text: '{text[:50]}...'")
        result = await self.provider.parse_transaction(text)
        logger.info(f"Parsed result: amount={result.amount}, category={result.category}")
        return result

    async def parse_receipt(self, ocr_text: str) -> list[ParsedTransaction]:
        """
        Parse OCR-extracted receipt text into transactions.

        Args:
            ocr_text: Text extracted from a receipt image via OCR.

        Returns:
            List of ParsedTransaction objects.
        """
        logger.info(f"Parsing receipt text ({len(ocr_text)} chars)")
        results = await self.provider.parse_receipt_text(ocr_text)
        logger.info(f"Parsed {len(results)} transaction(s) from receipt")
        return results

    async def parse_receipt_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> list[ParsedTransaction]:
        """
        Parse a receipt image directly into structured transactions.

        Args:
            image_bytes: Raw bytes of the receipt photo.
            mime_type: MIME type of the image, e.g., 'image/jpeg'

        Returns:
            List of ParsedTransaction objects.
        """
        logger.info("Parsing receipt image directly")
        results = await self.provider.parse_receipt_image(image_bytes, mime_type)
        logger.info(f"Parsed {len(results)} transaction(s) directly from receipt image")
        return results
