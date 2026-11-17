"""Audio capture into RAM (issue #7) following ADR 0006.

``devices``
    USB capture devices and native formats from ``/proc/asound``.
``capture``
    Fixed-size windows read from ``arecord`` into a reused buffer, with
    stall and disconnection detection, and level statistics.
``mic_check``
    Command line: ``python -m txori_kantua.audio.mic_check --help``.
"""
