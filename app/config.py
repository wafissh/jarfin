"""
Application configuration loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


# ── Default transaction categories ──────────────────────────────────────────

DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"name": "Makanan & Minuman", "name_en": "Food & Drinks", "examples": "Warteg, kopi, delivery"},
    {"name": "Transportasi", "name_en": "Transportation", "examples": "Grab, Gojek, bensin, parkir"},
    {"name": "Belanja", "name_en": "Shopping", "examples": "Supermarket, marketplace"},
    {"name": "Tagihan & Utilitas", "name_en": "Bills & Utilities", "examples": "Listrik, internet, pulsa"},
    {"name": "Hiburan", "name_en": "Entertainment", "examples": "Netflix, bioskop, game"},
    {"name": "Kesehatan", "name_en": "Health", "examples": "Apotek, dokter, gym"},
    {"name": "Lainnya", "name_en": "Others", "examples": "Tidak terkategori"},
]

CATEGORY_NAMES: list[str] = [cat["name"] for cat in DEFAULT_CATEGORIES]
CATEGORY_NAMES_EN: list[str] = [cat["name_en"] for cat in DEFAULT_CATEGORIES]


# ── Settings ────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram Bot API token from @BotFather")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./jarfin.db",
        description="Database connection URL",
    )

    # AI / Gemini
    gemini_api_key: str = Field(default="", description="Google Gemini API key")

    # AI / Groq
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model: str = Field(default="llama-3.3-70b-specdec", description="Groq AI model")

    # AI / Qwen
    dashscope_api_key: str = Field(default="", description="Alibaba DashScope / Qwen API Key")
    qwen_base_url: str = Field(default="", description="Qwen OpenAI-compatible base URL")
    qwen_model: str = Field(default="qwen3.5-plus", description="Qwen AI model")

    # Provider Selection
    ai_provider: Literal["gemini", "groq", "qwen"] = Field(
        default="gemini", description="AI Provider: 'gemini', 'groq', or 'qwen'"
    )

    # Google Cloud Vision (OCR)
    google_cloud_credentials: str = Field(
        default="", description="Path to Google Cloud service account JSON"
    )

    # Bot mode
    bot_mode: Literal["polling", "webhook"] = Field(
        default="polling", description="Bot mode: 'polling' for dev, 'webhook' for prod"
    )

    # Webhook (only for webhook mode)
    webhook_url: str = Field(default="", description="Public HTTPS URL for webhook")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Create and return a Settings instance."""
    return Settings()
