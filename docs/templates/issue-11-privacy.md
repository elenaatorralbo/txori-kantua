# Issue #11 — privacy audit report template

**Template only — not executed.** Copy to `docs/evidence/YYYY-MM-DD-issue-11-privacy.md` using the actual session date. Paste the Markdown printed by each command; never attach audio. Replace PENDING with observations; an unchecked criterion is not a pass.

- **Date (UTC):** PENDING
- **Run by:** PENDING
- **Reviewed by:** PENDING
- **Issue / PR:** #11 / PENDING
- **Commit:** PENDING (`git rev-parse HEAD`)
- **Hardware:** PENDING (Pi model, OS, architecture)
- **Relevant versions:** PENDING (Python, rpi-swap, systemd)
- **Procedure:** [privacy.md — Verification procedure](../privacy.md#verification-procedure); exact commands: PENDING
- **Expected result:** control detected; no FAIL in `system`; no audio in `files` or `payloads`.
- **Observed result:** PENDING
- **Limitations and pending tests:** PENDING

## 0. Safeguards installed

- `/etc/rpi/swap.conf.d/90-txori-zram-only.conf` present and rebooted after: PENDING
- `/etc/systemd/coredump.conf.d/90-txori-no-coredump.conf` present: PENDING
- `swapon --show` after reboot: PENDING

## 1. Control self-test

PENDING (output of `privacy.audit control /var/lib/txori-kantua` and `control /tmp`)

## 2. System checks

PENDING (output of `privacy.audit system`, and `--pid` of the audio process if it exists)

## 3. Files after a capture/inference run

- Test that was run between the marks (e.g. #7 ten windows): PENDING
- PENDING (output of `sudo privacy.audit files --since ...`)

## 4. MQTT payloads

PENDING (output of `mosquitto_sub ... | privacy.audit payloads --mqtt`, or "not run: broker #13 not available")

## 5. Logs and traffic

PENDING (output of `journalctl ... | privacy.audit payloads` and `ss -tunp`)

## Acceptance

- [ ] Policy forbids audio on disk, MQTT, API, logs and backups (privacy.md, ADR 0006) — reviewed by: PENDING
- [ ] The procedure detected the control file and the control payload on the Pi.
- [ ] Swap and core dumps cannot persist audio memory (`system` without FAIL after reboot).
