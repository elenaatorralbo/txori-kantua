"""Audio capture into RAM (issue #7) following ADR 0006.

``devices``
    USB capture devices and native formats from ``/proc/asound``.
``capture``
    Fixed-size windows read from ``arecord`` into a reused buffer, with
    stall and disconnection detection, and level statistics.
``mic_check``
    Command line: ``python -m txori_kantua.audio.mic_check --help``.
``birdnet``
    BirdNET V2.4 inference on one in-memory window (issue #8); needs the
    ``birdnet`` extra (numpy, ai-edge-litert).
``corpus``, ``benchmark``
    Authorised evaluation corpus and the feasibility benchmark:
    ``python -m txori_kantua.audio.benchmark --help``.
"""
