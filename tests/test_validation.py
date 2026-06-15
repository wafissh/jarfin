"""
Tests for message validation logic (length limits, app creation blocking, paper writing blocking).
"""

import pytest
from app.bot.handlers import _validate_message

def test_validate_message_valid_inputs():
    """Test standard valid messages (normal queries, transactions)."""
    # Simple transaction queries
    assert _validate_message("kopi 15000")[0] is True
    assert _validate_message("gaji masuk 5000000")[0] is True
    
    # Financial consulting queries
    assert _validate_message("bagaimana tips menabung 1 juta sebulan?")[0] is True
    assert _validate_message("apakah lebih baik beli mobil cash atau kredit?")[0] is True
    
    # Valid transactions mentioning paper/skripsi/koding with payment context
    assert _validate_message("bayar print skripsi 50000")[0] is True
    assert _validate_message("beli kertas buat paper 35000")[0] is True
    assert _validate_message("bayar jasa koding freelance 200000")[0] is True
    assert _validate_message("biaya cetak jurnal 150000")[0] is True
    assert _validate_message("fotokopi makalah 20000")[0] is True


def test_validate_message_too_long():
    """Test messages exceeding the 1000 character limit."""
    long_msg = "a" * 1001
    is_valid, warning = _validate_message(long_msg)
    assert is_valid is False
    assert "Pesan Terlalu Panjang" in warning
    
    # Normal short message is fine
    short_msg = "a" * 999
    assert _validate_message(short_msg)[0] is True


def test_validate_message_app_creation():
    """Test messages asking the AI to write source code or build applications/websites."""
    blocked_queries = [
        "bikin aplikasi kasir sederhana",
        "buat website e-commerce pake html css",
        "tolong buatkan program python untuk hitung gaji",
        "cara coding website dari awal",
        "buat kodingan calculator",
        "source code web toko online",
    ]
    for q in blocked_queries:
        is_valid, warning = _validate_message(q)
        assert is_valid is False, f"Query '{q}' should be blocked"
        assert "membuat aplikasi, program, atau koding" in warning


def test_validate_message_paper_writing():
    """Test messages asking the AI to write/prepare academic papers, theses, journals, essays."""
    blocked_queries = [
        "tolong buatkan skripsi tentang manajemen keuangan",
        "bikin paper mengenai dampak inflasi bagi umkm",
        "tulis esai bertema investasi masa kini",
        "tuliskan makalah dampak perang terhadap ekonomi",
        "paper tentang AI di bidang akuntansi",
        "skripsi tentang pengaruh suku bunga",
        "buat tesis sistem perpajakan indonesia",
    ]
    for q in blocked_queries:
        is_valid, warning = _validate_message(q)
        assert is_valid is False, f"Query '{q}' should be blocked"
        assert "menulis paper, skripsi, makalah, atau tugas akademik lainnya" in warning
