"""
Tests for the AI abstraction layer.
"""

import pytest
import asyncio
from datetime import date

from app.ai.base import AIProvider, ParsedTransaction


# ── Mock Provider ───────────────────────────────────────────────────────────

class MockAIProvider(AIProvider):
    """Mock AI provider for testing the abstraction layer."""

    async def parse_transaction(self, text: str) -> list[ParsedTransaction]:
        # Simple mock: extract the last number as amount
        import re
        numbers = re.findall(r"\d+", text)
        amount = float(numbers[-1]) if numbers else 0.0

        return [ParsedTransaction(
            amount=amount,
            category="Makanan & Minuman",
            description=text,
            transaction_date=date.today(),
            confidence=0.9,
        )]

    async def parse_receipt_text(self, ocr_text: str) -> list[ParsedTransaction]:
        return [
            ParsedTransaction(
                amount=50000,
                category="Belanja",
                merchant="Test Store",
                description="Receipt item",
                transaction_date=date.today(),
                confidence=0.8,
            )
        ]


# ── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_parse_transaction():
    """Test that a mock provider can parse a transaction."""
    provider = MockAIProvider()
    results = await provider.parse_transaction("Makan siang 25000")

    assert len(results) == 1
    assert results[0].amount == 25000
    assert results[0].category == "Makanan & Minuman"
    assert results[0].confidence == 0.9


@pytest.mark.asyncio
async def test_mock_provider_parse_receipt():
    """Test that a mock provider can parse receipt text."""
    provider = MockAIProvider()
    results = await provider.parse_receipt_text("Some receipt text")

    assert len(results) == 1
    assert results[0].amount == 50000
    assert results[0].merchant == "Test Store"


@pytest.mark.asyncio
async def test_parsed_transaction_to_dict():
    """Test ParsedTransaction serialization."""
    txn = ParsedTransaction(
        amount=35000,
        category="Transportasi",
        merchant="Grab",
        description="Grab ke kantor",
        transaction_date=date(2026, 6, 8),
        confidence=0.85,
    )

    d = txn.to_dict()
    assert d["amount"] == 35000
    assert d["category"] == "Transportasi"
    assert d["merchant"] == "Grab"
    assert d["transaction_date"] == "2026-06-08"
    assert d["confidence"] == 0.85


@pytest.mark.asyncio
async def test_provider_is_swappable():
    """Test that providers can be swapped via the abstraction layer."""
    from app.ai.parser import TransactionParser

    # Use mock provider
    parser = TransactionParser(provider=MockAIProvider())
    results = await parser.parse_text("Kopi 15000")

    assert len(results) == 1
    assert results[0].amount == 15000
    assert isinstance(results[0], ParsedTransaction)


@pytest.mark.asyncio
async def test_groq_provider_parse_transaction():
    """Test GroqProvider parsing a transaction via mocked HTTP client."""
    from app.ai.groq_provider import GroqProvider
    from unittest.mock import patch, AsyncMock
    import httpx

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"amount": 35000, "category": "Makanan & Minuman", "merchant": "Warteg", "description": "Makan siang", "transaction_date": "2026-06-10", "confidence": 0.95}'
                    }
                }
            ]
        },
        request=request
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = GroqProvider(api_key="test-key")
        results = await provider.parse_transaction("Makan warteg 35000")

        assert len(results) == 1
        assert results[0].amount == 35000
        assert results[0].category == "Makanan & Minuman"
        assert results[0].merchant == "Warteg"
        assert results[0].confidence == 0.95
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_groq_provider_parse_receipt():
    """Test GroqProvider parsing a receipt via mocked HTTP client."""
    from app.ai.groq_provider import GroqProvider
    from unittest.mock import patch, AsyncMock
    import httpx

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '[{"amount": 50000, "category": "Belanja", "merchant": "Indomaret", "description": "Kebutuhan harian", "transaction_date": "2026-06-10", "confidence": 0.9}]'
                    }
                }
            ]
        },
        request=request
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = GroqProvider(api_key="test-key")
        results = await provider.parse_receipt_text("Indomaret Belanja 50000")

        assert len(results) == 1
        assert results[0].amount == 50000
        assert results[0].category == "Belanja"
        assert results[0].merchant == "Indomaret"
        assert results[0].confidence == 0.9
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_qwen_provider_parse_transaction():
    """Test QwenProvider parsing a transaction via mocked HTTP client."""
    from app.ai.qwen_provider import QwenProvider
    from unittest.mock import patch
    import httpx

    request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"amount": 35000, "category": "Makanan & Minuman", "merchant": "Warteg", "description": "Makan siang", "transaction_date": "2026-06-10", "confidence": 0.95}'
                    }
                }
            ]
        },
        request=request
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = QwenProvider(api_key="test-key")
        results = await provider.parse_transaction("Makan warteg 35000")

        assert len(results) == 1
        assert results[0].amount == 35000
        assert results[0].category == "Makanan & Minuman"
        assert results[0].merchant == "Warteg"
        assert results[0].confidence == 0.95
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_qwen_provider_parse_receipt_image():
    """Test QwenProvider parsing a receipt image directly via mocked HTTP client."""
    from app.ai.qwen_provider import QwenProvider
    from unittest.mock import patch
    import httpx

    request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '[{"amount": 55000, "category": "Belanja", "merchant": "Alfamart", "description": "Belanja harian", "transaction_date": "2026-06-10", "confidence": 0.92}]'
                    }
                }
            ]
        },
        request=request
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = QwenProvider(api_key="test-key")
        results = await provider.parse_receipt_image(b"fake_image_bytes")

        assert len(results) == 1
        assert results[0].amount == 55000
        assert results[0].category == "Belanja"
        assert results[0].merchant == "Alfamart"
        assert results[0].confidence == 0.92
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_multi_transaction_parsing():
    """Test parsing multiple transactions using GeminiProvider with a mocked response."""
    from app.ai.gemini_provider import GeminiProvider
    from unittest.mock import patch
    import json
    
    mock_response_content = """[
        {"amount": 15000, "type": "expense", "category": "Makanan & Minuman", "merchant": "Starbucks", "description": "kopi", "transaction_date": "2026-06-16", "confidence": 0.9},
        {"amount": 25000, "type": "expense", "category": "Makanan & Minuman", "merchant": "Warteg", "description": "makan", "transaction_date": "2026-06-16", "confidence": 0.8},
        {"amount": 5000, "type": "expense", "category": "Transportasi", "merchant": "Parkir", "description": "parkir", "transaction_date": "2026-06-16", "confidence": 0.7}
    ]"""

    # Mock the google-genai Client response
    class MockResponse:
        def __init__(self, text):
            self.text = text

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.return_value = MockResponse(mock_response_content)

        provider = GeminiProvider(api_key="test-key")
        results = await provider.parse_transaction("kopi 15rb, makan 25rb, parkir 5rb")

        assert len(results) == 3
        
        assert results[0].amount == 15000
        assert results[0].merchant == "Starbucks"
        
        assert results[1].amount == 25000
        assert results[1].merchant == "Warteg"
        
        assert results[2].amount == 5000
        assert results[2].merchant == "Parkir"
        assert results[2].category == "Transportasi"


@pytest.mark.asyncio
async def test_transaction_service_parse_only_multi():
    """Test TransactionService.parse_only_multi returns structured dicts for multiple transactions."""
    from app.services.transaction_service import TransactionService
    from app.ai.parser import TransactionParser
    
    # Mock parser that returns multiple ParsedTransactions
    class MockParser:
        async def parse_text(self, text: str):
            return [
                ParsedTransaction(
                    amount=15000,
                    type="expense",
                    category="Makanan & Minuman",
                    merchant="Starbucks",
                    description="kopi",
                    transaction_date=date(2026, 6, 16),
                    confidence=0.9
                ),
                ParsedTransaction(
                    amount=25000,
                    type="expense",
                    category="Makanan & Minuman",
                    merchant="Warteg",
                    description="makan",
                    transaction_date=date(2026, 6, 16),
                    confidence=0.8
                )
            ]

    service = TransactionService(parser=MockParser())
    results = await service.parse_only_multi("kopi 15rb, makan 25rb")

    assert len(results) == 2
    assert results[0]["amount"] == 15000
    assert results[0]["merchant"] == "Starbucks"
    assert results[0]["date"] == "2026-06-16"
    assert results[1]["amount"] == 25000
    assert results[1]["merchant"] == "Warteg"
    assert results[1]["date"] == "2026-06-16"
