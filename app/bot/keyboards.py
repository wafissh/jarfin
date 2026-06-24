"""
Inline keyboard builders for the Telegram bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.config import DEFAULT_CATEGORIES, INCOME_CATEGORIES


def build_category_keyboard(txn_type: str = "expense") -> InlineKeyboardMarkup:
    """Build an inline keyboard with category selection buttons."""
    buttons = []
    categories = INCOME_CATEGORIES if txn_type == "income" else DEFAULT_CATEGORIES
    
    row = []
    for cat in categories:
        row.append(
            InlineKeyboardButton(
                text=f"{cat['name']}",
                callback_data=f"cat:{cat['name']}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_confirm_keyboard(transaction_id: str) -> InlineKeyboardMarkup:
    """Build confirm/cancel inline keyboard for a pending transaction.

    transaction_id here is a temporary key stored in context.user_data,
    not a database ID (since the txn hasn't been saved yet).
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Simpan", callback_data=f"confirm:{transaction_id}"),
            InlineKeyboardButton("❌ Batal", callback_data=f"cancel:{transaction_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Kategori", callback_data=f"editcat:{transaction_id}"),
        ],
    ])


def build_batch_confirm_keyboard(batch_id: str, item_count: int) -> InlineKeyboardMarkup:
    """Build confirm/cancel keyboard for a batch of multiple transactions.

    Includes per-item edit buttons so users can change category for individual items.
    """
    buttons = [
        [
            InlineKeyboardButton("✅ Simpan Semua", callback_data=f"batchconfirm:{batch_id}"),
            InlineKeyboardButton("❌ Batal Semua", callback_data=f"batchcancel:{batch_id}"),
        ],
    ]

    # Add per-item edit buttons (max 3 per row)
    edit_row = []
    for i in range(item_count):
        edit_row.append(
            InlineKeyboardButton(f"✏️ #{i+1}", callback_data=f"batchedit:{batch_id}:{i}")
        )
        if len(edit_row) == 3:
            buttons.append(edit_row)
            edit_row = []
    if edit_row:
        buttons.append(edit_row)

    return InlineKeyboardMarkup(buttons)


def build_batch_category_keyboard(batch_id: str, item_idx: int, txn_type: str = "expense") -> InlineKeyboardMarkup:
    """Build category keyboard for editing a specific item in a batch.

    Uses batchcat: callback format so the handler knows which batch and item to update.
    """
    buttons = []
    categories = INCOME_CATEGORIES if txn_type == "income" else DEFAULT_CATEGORIES

    row = []
    for cat in categories:
        row.append(
            InlineKeyboardButton(
                text=f"{cat['name']}",
                callback_data=f"batchcat:{batch_id}:{item_idx}:{cat['name']}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Add cancel button to go back to batch preview
    buttons.append([
        InlineKeyboardButton("↩️ Kembali", callback_data=f"batchback:{batch_id}")
    ])

    return InlineKeyboardMarkup(buttons)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Ringkasan", callback_data="menu:summary"),
            InlineKeyboardButton("📝 Riwayat", callback_data="menu:history"),
        ],
        [
            InlineKeyboardButton("💰 Budget", callback_data="menu:budget"),
            InlineKeyboardButton("🔄 Rutin", callback_data="menu:recurring"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
            InlineKeyboardButton("❓ Bantuan", callback_data="menu:help"),
        ],
    ])


# ── Settings Keyboards ──────────────────────────────────────────────────────

SUPPORTED_CURRENCIES = ["IDR", "USD", "EUR", "SGD", "MYR", "JPY"]
SUPPORTED_TIMEZONES = [
    ("WIB (UTC+7)", "Asia/Jakarta"),
    ("WITA (UTC+8)", "Asia/Makassar"),
    ("WIT (UTC+9)", "Asia/Jayapura"),
    ("UTC", "UTC"),
]


def build_settings_keyboard() -> InlineKeyboardMarkup:
    """Build settings menu keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💱 Mata Uang", callback_data="settings:currency"),
            InlineKeyboardButton("🕐 Zona Waktu", callback_data="settings:timezone"),
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data="menu:main"),
        ],
    ])


def build_currency_keyboard() -> InlineKeyboardMarkup:
    """Build currency selection keyboard."""
    buttons = []
    row = []
    for i, currency in enumerate(SUPPORTED_CURRENCIES):
        row.append(
            InlineKeyboardButton(currency, callback_data=f"setcurrency:{currency}")
        )
        if len(row) == 3:  # 3 buttons per row
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="menu:settings")])
    return InlineKeyboardMarkup(buttons)


def build_timezone_keyboard() -> InlineKeyboardMarkup:
    """Build timezone selection keyboard."""
    buttons = []
    for label, tz_name in SUPPORTED_TIMEZONES:
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"settz:{tz_name}")]
        )
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="menu:settings")])
    return InlineKeyboardMarkup(buttons)


# ── Budget Keyboards ────────────────────────────────────────────────────────

def build_budget_category_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting a category to set budget for."""
    buttons = []
    for cat in DEFAULT_CATEGORIES:
        if cat["name"] != "Lainnya":  # Don't budget "Lainnya"
            buttons.append(
                [InlineKeyboardButton(
                    text=cat["name"],
                    callback_data=f"budgetcat:{cat['name']}",
                )]
            )
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="menu:budget")])
    return InlineKeyboardMarkup(buttons)


def build_budget_menu_keyboard() -> InlineKeyboardMarkup:
    """Build budget main menu keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Lihat Budget", callback_data="budget:view"),
            InlineKeyboardButton("➕ Set Budget", callback_data="budget:set"),
        ],
        [
            InlineKeyboardButton("🗑️ Hapus Budget", callback_data="budget:delete_select"),
            InlineKeyboardButton("📋 Copy ke Bulan Depan", callback_data="budget:copy_next"),
        ],
        [
            InlineKeyboardButton("🔙 Menu Utama", callback_data="menu:main"),
        ],
    ])


def build_budget_delete_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting a budget category to delete."""
    buttons = []
    for cat in DEFAULT_CATEGORIES:
        if cat["name"] != "Lainnya":
            buttons.append(
                [InlineKeyboardButton(
                    text=f"🗑️ {cat['name']}",
                    callback_data=f"budget_del:{cat['name']}",
                )]
            )
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="budget:view")])
    return InlineKeyboardMarkup(buttons)


def build_budget_delete_confirm_keyboard(category: str) -> InlineKeyboardMarkup:
    """Build confirm/cancel keyboard for budget deletion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗑️ Ya, Hapus",
                callback_data=f"budget_del_confirm:{category}",
            ),
            InlineKeyboardButton("❌ Batal", callback_data="budget:view"),
        ],
    ])


# ── History Keyboards ───────────────────────────────────────────────────────

def build_history_period_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting history period."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Hari Ini", callback_data="history:hari ini"),
            InlineKeyboardButton("📅 Minggu Ini", callback_data="history:minggu ini"),
        ],
        [
            InlineKeyboardButton("📅 Bulan Ini", callback_data="history:bulan ini"),
            InlineKeyboardButton("🕐 Terbaru", callback_data="history:recent"),
        ],
        [
            InlineKeyboardButton("🔙 Menu Utama", callback_data="menu:main"),
        ],
    ])


def build_history_nav_keyboard(period: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Build history navigation keyboard with prev/next pagination."""
    nav_row = []

    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"histpage:{period}:{page - 1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )

    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"histpage:{period}:{page + 1}")
        )

    return InlineKeyboardMarkup([
        nav_row,
        [InlineKeyboardButton("🔙 Pilih Periode", callback_data="menu:history")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu:main")],
    ])


# ── Delete Transaction Keyboards ────────────────────────────────────────────

def build_delete_confirm_keyboard(txn_id: int) -> InlineKeyboardMarkup:
    """Build confirm/cancel keyboard for transaction deletion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗑️ Ya, Hapus",
                callback_data=f"delete_confirm:{txn_id}",
            ),
            InlineKeyboardButton("❌ Batal", callback_data="menu:history"),
        ],
    ])


# ── Recurring Transaction Keyboards ────────────────────────────────────────

def build_recurring_menu_keyboard() -> InlineKeyboardMarkup:
    """Build recurring transactions menu keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Lihat Rutin", callback_data="recurring:list"),
            InlineKeyboardButton("➕ Tambah Rutin", callback_data="recurring:add"),
        ],
        [
            InlineKeyboardButton("🔙 Menu Utama", callback_data="menu:main"),
        ],
    ])


def build_recurring_category_keyboard() -> InlineKeyboardMarkup:
    """Build category keyboard for recurring transaction setup."""
    buttons = []
    for cat in DEFAULT_CATEGORIES:
        buttons.append(
            [InlineKeyboardButton(
                text=cat["name"],
                callback_data=f"reccat:{cat['name']}",
            )]
        )
    buttons.append([InlineKeyboardButton("🔙 Batal", callback_data="menu:recurring")])
    return InlineKeyboardMarkup(buttons)


def build_recurring_frequency_keyboard() -> InlineKeyboardMarkup:
    """Build frequency selection keyboard for recurring transactions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Bulanan", callback_data="recfreq:monthly"),
            InlineKeyboardButton("📅 Mingguan", callback_data="recfreq:weekly"),
        ],
        [
            InlineKeyboardButton("📅 Harian", callback_data="recfreq:daily"),
        ],
        [
            InlineKeyboardButton("🔙 Batal", callback_data="menu:recurring"),
        ],
    ])


def build_recurring_item_keyboard(rec_id: int) -> InlineKeyboardMarkup:
    """Build action keyboard for a specific recurring transaction."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗑️ Hapus",
                callback_data=f"rec_delete:{rec_id}",
            ),
            InlineKeyboardButton(
                "✅ Eksekusi Sekarang",
                callback_data=f"rec_exec:{rec_id}",
            ),
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data="recurring:list"),
        ],
    ])
