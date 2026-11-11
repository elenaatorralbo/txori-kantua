"""Desktop tests only: these do not certify the physical LCD or its ROM."""

import pytest

from txori_kantua.lcd import normalize_text, paginate_text


@pytest.mark.parametrize(("text", "expected"), [
    ("Herrerillo común", "Herrerillo comun"),
    ("Amilotx urdina", "Amilotx urdina"),
    ("Blue tit", "Blue tit"),
    ("Ñandú, pingüino", "Nandu, pinguino"),
    ("comu\u0301n", "comun"),
    ("  ave\n\tcomún\r\n", "ave comun"),
    ("‘Ave’ — œ …", "'Ave' - oe ..."),
    ("Ave 🐦\x00", "Ave ??"),
])
def test_character_policy(text, expected):
    assert normalize_text(text) == expected


def test_short_name_clears_both_rows():
    assert paginate_text("Blue tit") == (("Blue tit        ", "                "),)


def test_word_wrapping_and_pagination_preserve_name():
    assert paginate_text("Carbonero comun / Parus major / Great tit") == (
        ("Carbonero comun ", "/ Parus major / "),
        ("Great tit       ", "                "),
    )


@pytest.mark.parametrize("length", [16, 17, 32, 33, 64, 65])
def test_long_unbroken_name_is_not_truncated(length):
    text = "A" * length
    pages = paginate_text(text)
    assert len(pages) == (length + 31) // 32
    assert "".join(row.rstrip() for page in pages for row in page) == text
    assert all(len(page) == 2 for page in pages)
    assert all(len(row) == 16 for page in pages for row in page)


@pytest.mark.parametrize("text", ["", " \t\n"])
def test_empty_text_returns_a_blank_screen(text):
    assert paginate_text(text) == ((" " * 16, " " * 16),)


def test_output_contains_only_printable_ascii():
    pages = paginate_text("Águila 🐦 — nombre muy largo con\ncaracteres 特殊")
    assert all(32 <= ord(char) <= 126 for page in pages for row in page for char in row)
