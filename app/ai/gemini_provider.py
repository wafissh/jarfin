"""
Gemini AI provider implementation.

Uses Google's Gemini API to parse transaction text
and receipt OCR output into structured data.
"""

import json
import logging
from datetime import date, datetime
from typing import Any

from app.ai.base import AIProvider, ParsedTransaction
from app.config import CATEGORY_NAMES, INCOME_CATEGORY_NAMES, get_settings

logger = logging.getLogger(__name__)

# ── Prompt Templates ────────────────────────────────────────────────────────

TRANSACTION_PARSE_PROMPT = """Kamu adalah asisten keuangan. Tugas kamu: ekstrak SEMUA informasi transaksi dari pesan pengguna.

PENTING: Satu pesan bisa berisi SATU atau BANYAK transaksi. Deteksi setiap transaksi individual yang disebutkan.

Daftar Kategori yang tersedia berdasarkan tipe transaksi:
- Kategori Pengeluaran (Expense): {expense_categories}
- Kategori Pemasukan (Income): {income_categories}

Pesan pengguna: "{text}"

Tanggal hari ini: {today}

Balas dalam format JSON array (tanpa markdown, tanpa ```):
[
  {{
    "amount": <angka>,
    "type": "<"expense" atau "income">",
    "category": "<kategori dari daftar>",
    "merchant": "<nama toko/tempat atau null>",
    "description": "<deskripsi singkat>",
    "transaction_date": "<YYYY-MM-DD>",
    "confidence": <0.0-1.0>
  }}
]

Aturan:
- PENTING: Jika pesan berupa pertanyaan, konsultasi keuangan, tips menabung/investasi, curhat, sapaan, atau diskusi umum yang BUKAN pencatatan transaksi riil/langsung (misal: "gmn cara aku nabung...", "bagaimana cara...", "halo", dll.), kamu WAJIB mengembalikan array kosong `[]` (atau set `confidence` = 0.0) agar sistem tahu ini adalah konsultasi/chat biasa, bukan transaksi untuk dicatat.
- Hanya catat jika pengguna secara spesifik ingin mencatat transaksi pemasukan atau pengeluaran riil (misal: "kopi 15rb", "beli bensin 50000", "gaji masuk 5jt", "skrg aku punya cash 5 ribu, bank 180 ribu").
- SELALU balas dalam format JSON array, meskipun hanya ada 1 transaksi atau kosong `[]`
- Jika ada banyak transaksi dalam satu pesan (misal: "kopi 15rb, makan 25rb, parkir 5rb"), buat satu objek per transaksi
- amount harus berupa angka positif
- type harus berupa "income" jika transaksi adalah pemasukan (gaji, transfer masuk, dapat uang, kembalian, untung, hadiah, dll) atau "expense" jika transaksi adalah pengeluaran (belanja, makan, bayar tagihan, dll)
- category harus disesuaikan dengan tipe transaksi. Jika type adalah "income", category harus dipilih dari Kategori Pemasukan. Jika type adalah "expense", category harus dipilih dari Kategori Pengeluaran.
- Jika pengguna tidak menyebut tanggal, gunakan hari ini
- Jika tidak yakin kategori, gunakan "Lainnya"
- confidence: seberapa yakin kamu dengan parsing ini (0.0-1.0). Jika pesan terindikasi bukan transaksi riil tetapi kamu memparsingnya, beri `confidence` = 0.0.
"""

RECEIPT_PARSE_PROMPT = """Kamu adalah asisten keuangan. Ekstrak semua transaksi dari teks struk/nota berikut.

Daftar Kategori yang tersedia berdasarkan tipe transaksi:
- Kategori Pengeluaran (Expense): {expense_categories}
- Kategori Pemasukan (Income): {income_categories}

Teks struk:
\"\"\"
{ocr_text}
\"\"\"

Tanggal hari ini: {today}

Balas dalam format JSON array (tanpa markdown, tanpa ```):
[
  {{
    "amount": <angka>,
    "type": "<"expense" atau "income">",
    "category": "<kategori dari daftar>",
    "merchant": "<nama toko>",
    "description": "<item/deskripsi>",
    "transaction_date": "<YYYY-MM-DD>",
    "confidence": <0.0-1.0>
  }}
]

Aturan:
- Jika ada total, buat 1 transaksi dengan total tersebut
- Jika ada item-item individual, buat transaksi per item
- Gunakan nama toko dari struk sebagai merchant
- type harus berupa "expense" untuk pengeluaran belanja struk, kecuali terindikasi sebaliknya
- category harus disesuaikan dengan tipe transaksi. Jika type adalah "income", category harus dipilih dari Kategori Pemasukan. Jika type adalah "expense", category harus dipilih dari Kategori Pengeluaran.
"""


# ── Gemini Provider ─────────────────────────────────────────────────────────

class GeminiProvider(AIProvider):
    """AI provider using Google Gemini API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().gemini_api_key
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Gemini client."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def parse_transaction(self, text: str) -> list[ParsedTransaction]:
        """Parse a text message into structured transaction(s) using Gemini."""
        prompt = TRANSACTION_PARSE_PROMPT.format(
            expense_categories=", ".join(CATEGORY_NAMES),
            income_categories=", ".join(INCOME_CATEGORY_NAMES),
            text=text,
            today=date.today().isoformat(),
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )

            return self._parse_json_list_response(response.text)

        except Exception as e:
            logger.error(f"Gemini parse_transaction failed: {e}")
            # Fallback: try to extract amount from text
            return [self._fallback_parse(text)]

    async def parse_receipt_text(self, ocr_text: str) -> list[ParsedTransaction]:
        """Parse OCR receipt text into transactions using Gemini."""
        prompt = RECEIPT_PARSE_PROMPT.format(
            expense_categories=", ".join(CATEGORY_NAMES),
            income_categories=", ".join(INCOME_CATEGORY_NAMES),
            ocr_text=ocr_text,
            today=date.today().isoformat(),
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )

            return self._parse_json_list_response(response.text)

        except Exception as e:
            logger.error(f"Gemini parse_receipt_text failed: {e}")
            return []

    # ── Internal Helpers ────────────────────────────────────────────────

    def _parse_json_response(self, raw: str) -> ParsedTransaction:
        """Parse a single JSON object from Gemini response."""
        # Clean up response (remove markdown code blocks if present)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        return self._dict_to_parsed(data)

    def _parse_json_list_response(self, raw: str) -> list[ParsedTransaction]:
        """Parse a JSON array from Gemini response."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        if isinstance(data, list):
            return [self._dict_to_parsed(item) for item in data]
        return [self._dict_to_parsed(data)]

    def _dict_to_parsed(self, data: dict[str, Any]) -> ParsedTransaction:
        """Convert a dict to ParsedTransaction."""
        txn_date = None
        if data.get("transaction_date"):
            try:
                txn_date = datetime.strptime(data["transaction_date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                txn_date = date.today()

        return ParsedTransaction(
            amount=float(data.get("amount", 0)),
            type=data.get("type", "expense"),
            category=data.get("category", "Lainnya"),
            merchant=data.get("merchant"),
            description=data.get("description"),
            transaction_date=txn_date or date.today(),
            confidence=float(data.get("confidence", 0.5)),
        )

    def _fallback_parse(self, text: str) -> ParsedTransaction:
        """Simple fallback when AI fails: extract numbers from text."""
        import re

        numbers = re.findall(r"[\d.,]+", text.replace(".", "").replace(",", ""))
        amount = 0.0
        for num in numbers:
            try:
                val = float(num)
                if val > amount:
                    amount = val
            except ValueError:
                continue

        type_val = "expense"
        lower_text = text.lower()
        if any(w in lower_text for w in ["gaji", "pemasukan", "dapat", "terima", "transfer masuk", "income", "payroll", "bonus", "kembalian"]):
            type_val = "income"

        return ParsedTransaction(
            amount=amount,
            type=type_val,
            category="Lainnya",
            description=text[:100],
            transaction_date=date.today(),
            confidence=0.1,
        )
