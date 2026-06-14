"""
OCR service — stub untuk Qwen-only mode.

Karena bot menggunakan Qwen multimodal yang bisa langsung parse gambar,
Google Cloud Vision OCR tidak diperlukan. Service ini tetap ada untuk
kompatibilitas arsitektur, tapi akan selalu return None (kosong)
sehingga handler akan fall through ke direct image parsing Qwen.
"""

import logging

logger = logging.getLogger(__name__)


class OCRService:
    """
    OCR service stub.

    Dalam konfigurasi saat ini (AI_PROVIDER=qwen), foto struk diproses
    langsung oleh QwenProvider.parse_receipt_image() tanpa melewati OCR.
    Service ini dipertahankan untuk forward-compatibility jika suatu saat
    akan diintegrasikan dengan Google Cloud Vision atau Tesseract.
    """

    def __init__(self, credentials_path: str | None = None):
        self.credentials_path = credentials_path
        self._client = None

    async def extract_text(self, image_bytes: bytes) -> str | None:
        """
        Extract text from an image using OCR.

        Returns:
            None — Qwen multimodal digunakan sebagai gantinya.
        """
        logger.debug(
            "OCR service dipanggil tapi tidak aktif (Qwen multimodal digunakan). "
            "Return None agar handler fall through ke direct image parsing."
        )
        return None
