"""Open an I2C bus with the smbus interface (``smbus2``, or ``smbus`` as fallback).

Both drivers in this package only need ``read_byte_data``,
``read_i2c_block_data``, ``write_byte_data``, ``write_byte`` and
``read_word_data``, so tests pass a fake object with those methods instead.
"""

from __future__ import annotations

from typing import Any

#: I2C bus of the 40-pin header on the Raspberry Pi 5 (and of the Grove Base Hat).
DEFAULT_BUS = 1


def open_bus(number: int = DEFAULT_BUS) -> Any:
    try:
        from smbus2 import SMBus
    except ImportError:
        try:
            from smbus import SMBus  # type: ignore[no-redef]
        except ImportError as exc:
            raise ImportError("install smbus2 (python3-smbus2) to read I2C sensors") from exc
    return SMBus(number)
