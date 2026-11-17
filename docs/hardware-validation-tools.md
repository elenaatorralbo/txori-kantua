# Physical validation tools for issues #5 and #6

These tools collect observations; they do not mark any acceptance criterion as
passed. Follow [the session guide](sprint1-hardware-session.md) and complete the
existing [input](templates/issue-5-inputs.md) and [LCD](templates/issue-6-lcd.md)
reports. Record commit, interpreter/driver versions, exact command, hardware,
operator and independent reviewer. Store only sanitised logs/photos.

## Inputs

Use the Pi environment that already has `lgpio`. From the repository root,
`PYTHONPATH=src python tools/check_inputs.py --help` lists required parameters.
Supply the identified gpiochip and BCM GPIO offsets, measured active polarities,
PIR warmup and touch debounce. No pins, pull resistors or electrical polarity are
assumed. The program only claims input lines and releases them on exit; stop any
other process using those GPIOs first. Never guess the wiring from port labels.

Redirect stdout to a new CSV file. Every sample records UTC, elapsed monotonic
milliseconds, logical input levels, PIR state and both action flags. Default
capture is five minutes at a requested 5 ms polling interval; actual timestamps
show scheduler delays. Pulses shorter than the polling interval can be missed.
Read errors terminate the run; a plain GPIO level cannot identify unplugging.

After warmup, perform ten presence/absence cycles and ten touch/release cycles,
including held inputs. Record the operator-observed cycle times separately and
compare each against action flags in the CSV. An action count alone does not
prove ten physical cycles or exclude false triggers. Record an idle interval
and its false-trigger count. For disconnect checks, power down before changing
connections and run a separately labelled capture after restarting. Record the
actual observed levels and limitations, not an invented unavailable signal.

## LCD

Use only for the JHD1802 driver already used by `txori_kantua.station`. Confirm
the actual model first. Stop the station service/timer before taking ownership
of the LCD, remembering their previous state so it can be restored afterwards.
Run from the repository root in the existing Grove-enabled Pi environment:

```bash
PYTHONPATH=src python tools/check_lcd.py
```

Each Enter advances after you have photographed and recorded the current page:
two full rows, accented name transliteration, long-name pages and short-name
overwrite. Every row is padded to 16 ASCII characters. Exit clears the display.
Run the command again to test process restart, photographing the recovered rows.

This script does not assume RGB/backlight methods: verify the exact hardware's
supported controls through its installed driver, record unsupported features
explicitly, and exercise supported controls separately. A successful I2C write
is not proof that text is visible. Retain photographs/video and actual results.

## Desktop verification

`python -m pytest tests/test_hardware_checks.py tests/test_lcd.py tests/test_pir.py tests/test_touch.py`
uses synthetic inputs and a fake display. It is not physical acceptance evidence.
