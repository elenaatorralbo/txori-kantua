"""Buffers passed to a logger never reach the formatted output."""

import array
import io
import logging

import pytest

from txori_kantua.privacy.log_guard import AudioLogFilter, install

SECRET = b"\x01\x02SAMPLES\x03" * 100


@pytest.fixture
def logger():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger(f"guard-test-{id(stream)}")
    log.propagate = False
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    install(log)
    yield log, stream
    log.removeHandler(handler)


@pytest.mark.parametrize("value", [
    SECRET, bytearray(SECRET), memoryview(SECRET), array.array("h", range(500)),
])
def test_buffer_arguments_are_redacted(logger, value):
    log, stream = logger
    log.info("window %s captured", value)
    output = stream.getvalue()
    assert "SAMPLES" not in output and "499" not in output
    assert "<redacted" in output and "captured" in output


def test_buffer_as_message_is_redacted(logger):
    log, stream = logger
    log.warning(SECRET)
    assert "SAMPLES" not in stream.getvalue()


def test_mapping_arguments_are_redacted(logger):
    log, stream = logger
    log.info("%(n)d bytes: %(data)s", {"n": 3, "data": SECRET})
    assert stream.getvalue().startswith("3 bytes: <redacted bytes of 1000 bytes>")


def test_ordinary_arguments_are_untouched(logger):
    log, stream = logger
    log.info("window %d: rms %.1f dBFS, device %s", 3, -42.5, "hw:CARD=Device,DEV=0")
    assert stream.getvalue() == "window 3: rms -42.5 dBFS, device hw:CARD=Device,DEV=0\n"


def test_array_like_objects_without_importing_numpy():
    class FakeArray:
        __array_interface__ = {}
        size = 144000
        nbytes = 576000

    record = logging.LogRecord("x", logging.INFO, __file__, 1, "%s", (FakeArray(),), None)
    AudioLogFilter().filter(record)
    assert record.getMessage() == "<redacted FakeArray of 576000 bytes>"


def test_install_is_idempotent(logger):
    log, _ = logger
    install(log)
    assert sum(isinstance(f, AudioLogFilter) for f in log.handlers[0].filters) == 1
