# Fino 🤖💰

Telegram bot pencatat keuangan otomatis dengan AI.

## Fitur

- 💬 **Catat via teks** — Kirim pesan seperti "Makan siang 25000" dan bot akan mencatat otomatis
- 📷 **Catat via foto** — Kirim foto struk/nota dan bot akan membaca dengan OCR + AI
- 📊 **Ringkasan** — Lihat ringkasan pengeluaran per kategori per bulan
- 🤖 **AI Parsing** — AI untuk mengekstrak informasi transaksi secara cerdas
- 🔄 **Multi-platform** — Desain siap untuk Telegram & WhatsApp

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Server | Python + FastAPI |
| Telegram SDK | python-telegram-bot v21+ |
| Database | SQLite (dev) → Supabase PostgreSQL (prod) |
| OCR | Google Cloud Vision API |
| AI Parsing | Gemini / Groq / Qwen (swappable) |

## Quick Start

### 1. Setup

```bash
# Clone & masuk ke folder project
cd "CATAT AI"

# Buat virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Konfigurasi

```bash
# Copy template env
copy .env.example .env

# Edit .env dan isi:
# - TELEGRAM_BOT_TOKEN (dari @BotFather di Telegram)
# - GEMINI_API_KEY (dari Google AI Studio)
```

### 3. Jalankan

```bash
# Development (polling mode)
python -m app.main
```

Bot akan berjalan di polling mode dan FastAPI di `http://localhost:8000`.

## Deploy ke Production

### Persiapan Supabase

1. Buat project di [Supabase](https://supabase.com)
2. Buka **Settings → Database → Connection string → URI**
3. Copy URI dan ganti `[YOUR-PASSWORD]` dengan password database kamu
4. Ubah prefix dari `postgresql://` menjadi `postgresql+asyncpg://`
5. Set `DATABASE_URL` di environment variable platform deploy kamu

### Deploy ke Railway

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login & init
railway login
railway init

# 3. Set environment variables
railway variables set TELEGRAM_BOT_TOKEN=xxx
railway variables set DATABASE_URL=postgresql+asyncpg://...
railway variables set AI_PROVIDER=qwen
railway variables set DASHSCOPE_API_KEY=xxx
railway variables set BOT_MODE=webhook
railway variables set WEBHOOK_URL=https://your-app.up.railway.app

# 4. Deploy
railway up
```

### Deploy ke Render

1. Buat **Web Service** baru di [Render](https://render.com)
2. Connect repository GitHub kamu
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Tambah environment variables di tab **Environment**

### Deploy dengan Docker (VPS)

```bash
# Build image
docker build -t jarfin .

# Run container
docker run -d \
  --name jarfin \
  -p 8000:8000 \
  --env-file .env \
  jarfin
```

## Struktur Project

```
app/
├── main.py           # FastAPI + bot startup
├── config.py         # Environment & settings
├── bot/
│   ├── handlers.py   # Telegram handlers
│   └── keyboards.py  # Inline keyboards
├── db/
│   ├── database.py   # SQLAlchemy engine
│   ├── models.py     # ORM models
│   └── repositories.py  # CRUD operations
├── services/
│   ├── transaction_service.py  # Business logic
│   └── ocr_service.py         # OCR processing
└── ai/
    ├── base.py             # Abstract AI provider
    ├── gemini_provider.py  # Gemini implementation
    └── parser.py           # AI parser (DI)
```

## Kategori Default

| Kategori | Contoh |
|----------|--------|
| 🍔 Makanan & Minuman | Warteg, kopi, delivery |
| 🚗 Transportasi | Grab, Gojek, bensin |
| 🛒 Belanja | Supermarket, marketplace |
| 💡 Tagihan & Utilitas | Listrik, internet, pulsa |
| 🎮 Hiburan | Netflix, bioskop, game |
| 🏥 Kesehatan | Apotek, dokter, gym |
| 📦 Lainnya | Tidak terkategori |

## Mengganti AI Provider

Arsitektur menggunakan abstraction layer sehingga bisa swap AI model tanpa ubah kode:

```python
# Default: Gemini
from app.ai.gemini_provider import GeminiProvider
parser = TransactionParser(provider=GeminiProvider())

# Swap ke provider lain (contoh):
from app.ai.openai_provider import OpenAIProvider
parser = TransactionParser(provider=OpenAIProvider())
```

Cukup implement interface `AIProvider` di `app/ai/base.py`.
