"""Hardware-independent text pages for the Grove 16x2 LCD (issue #6).

Only printable ASCII is emitted until the physical display's character ROM
has been verified. This module neither controls the display nor times pages.
"""

from __future__ import annotations

import argparse
import textwrap
import unicodedata

LCD_COLUMNS = 16
LCD_ROWS = 2

_REPLACEMENTS = str.maketrans({
    "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "ß": "ss",
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...",
})


def normalize_text(text: str) -> str:
    """Transliterate accents, collapse whitespace and replace unknowns with ?.

    Newlines are word separators, not commands to position the LCD cursor.
    Unsupported symbols and control characters are visible as question marks.
    """
    decomposed = unicodedata.normalize("NFKD", text.translate(_REPLACEMENTS))
    characters = []
    for character in decomposed:
        if unicodedata.category(character).startswith("M"):
            continue
        if character.isspace():
            characters.append(" ")
        elif " " <= character <= "~":
            characters.append(character)
        else:
            characters.append("?")
    return " ".join("".join(characters).split())


def paginate_text(text: str) -> tuple[tuple[str, str], ...]:
    """Return immutable pages, each with two space-padded 16-character rows.

    Prefer whole words; split words longer than a row without truncating them.
    Empty input yields one blank page, so a caller can clear previous content.
    Padding every row also clears trailing characters from earlier messages.
    """
    lines = textwrap.wrap(
        normalize_text(text), width=LCD_COLUMNS, break_long_words=True,
        break_on_hyphens=False,
    ) or [""]
    if len(lines) % LCD_ROWS:
        lines.append("")
    return tuple(
        (lines[index].ljust(LCD_COLUMNS), lines[index + 1].ljust(LCD_COLUMNS))
        for index in range(0, len(lines), LCD_ROWS)
    )


def main() -> None:
    """Print a terminal preview; no GPIO, I2C or hardware libraries needed."""
    parser = argparse.ArgumentParser(description="Preview text on a simulated 16x2 LCD")
    parser.add_argument("text", help="Text to paginate (quote text containing spaces)")
    args = parser.parse_args()
    pages = paginate_text(args.text)
    for number, page in enumerate(pages, start=1):
        print(f"Page {number}/{len(pages)}")
        print("+----------------+")
        for row in page:
            print(f"|{row}|")
        print("+----------------+")


if __name__ == "__main__":
    main()
