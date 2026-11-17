"""Station health monitor (issue #24).

- :mod:`.metrics`: CPU, memory, SoC temperature, free disk and uptime read
  from ``/proc`` and ``/sys``; a metric that cannot be read is ``None``.
- :mod:`.services`: declared status of each systemd unit (healthy, degraded,
  failed). A stopped service is not healthy.
- :mod:`.jsonlog`: one JSON object per log line, with ``event_id``.
- :mod:`.monitor`: builds the contract ``health`` event every interval.
"""
