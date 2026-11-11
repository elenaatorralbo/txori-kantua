# LCD text formatting — desktop implementation

Partial implementation for [issue #6](https://github.com/elenaatorralbo/txori-kantua/issues/6).
The text formatter runs without a Raspberry Pi, wiring information or hardware
libraries. Physical display validation remains pending.

See the [detection contract review](lcd-contract-review.md) for desktop
compatibility checks and the remaining station interface decisions.

## Text policy

- Each page contains two rows of exactly 16 characters, padded with spaces to
  overwrite any leftover text from the previous page.
- Words stay together when they fit. Longer words are split across rows.
  Text continues on additional pages instead of being truncated.
- Accents are transliterated: `Herrerillo común` becomes `Herrerillo comun`.
  The same policy applies to ES/EU/EN text; this module does not translate names.
- Whitespace, including line breaks, becomes a word separator. Common typographic
  punctuation is converted to ASCII. Unsupported symbols become `?`.
- Empty text produces a blank page. There is no automatic page timer or touch
  handling; the station controller will choose which page to display in #22.

Printable ASCII is a provisional baseline until the real LCD character set is
checked. Preserve original names in the application; transliterate only for display.

## Run on a computer

From the repository root, using Python 3.11 or newer:

```bash
PYTHONPATH=src python -m txori_kantua.lcd "Carbonero común / Parus major / Great tit"
```

The terminal prints bordered previews of every page. It does not access hardware.

For use by a future hardware adapter:

```python
from txori_kantua.lcd import paginate_text

pages = paginate_text("Herrerillo común")
first_row, second_row = pages[0]
```

To run the desktop tests in an environment with the development dependencies:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_lcd.py
```

## Remaining physical checks for #6

Record the exact LCD model, driver version and wiring when available. Then
verify two visible lines, colours, backlight off, accented and long names using
this policy, and recovery after restarting the test. Attach photos or video and
observations. Desktop tests do not complete these acceptance criteria.
