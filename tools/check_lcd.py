"""Interactive physical JHD1802 text checks for #6; observations remain manual."""
from txori_kantua.lcd import paginate_text


def cases():
    yield 'Two full rows', ('1234567890ABCDEF', 'abcdefghijklmnop')
    for text in ('Herrerillo común', 'Carbonero común / Parus major / Great tit', 'Blue tit'):
        for i, page in enumerate(paginate_text(text), 1):
            yield f'{text}, page {i}', page


def run(lcd, confirm=input):
    try:
        for title, rows in cases():
            for row, text in enumerate(rows):
                lcd.setCursor(row, 0)
                lcd.write(text)
            confirm(f'{title}: {rows!r}. Photograph and record actual result; Enter for next: ')
    finally:
        lcd.clear()


if __name__ == '__main__':
    from grove.display.jhd1802 import JHD1802
    run(JHD1802())
