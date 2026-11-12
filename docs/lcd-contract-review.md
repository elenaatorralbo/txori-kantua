# Detection contract review for the LCD — 11 November 2026

Refs [#10](https://github.com/elenaatorralbo/txori-kantua/issues/10) and
[#6](https://github.com/elenaatorralbo/txori-kantua/issues/6).
This is a desktop consumer compatibility review, not team approval of all
contracts or evidence from the Raspberry Pi.

## Verified compatibility

The three repository detection examples pass through the public messaging
encoder/decoder and the LCD formatter. All display `Turdus merula` on the first
line, padded to 16 characters, with a blank second line. The source event is
unchanged. No schema change is needed for this scientific-name fallback.

Additional checks cover the optional taxonomic key, a synthetic long name
that spans pages, invalid common names, station mismatch and replay of the
same event. Replay preserves identity, observation time and formatted text;
these tests do not implement consumer deduplication or expiry.

| Contract field / rule | LCD implication |
|---|---|
| `species.scientific_name` is required | A scientific-name fallback is always available after validation. |
| `species.taxon_key` is optional | Display must work without it. |
| Common names are not MQTT fields | ES/EU/EN names need a separate reviewed catalogue keyed by scientific name. |
| `confidence` is a model score from 0 to 1 | If displayed later, label it as a score, not a probability or confirmed identification. |
| `observed_at` is the start of the observation window | Use observation time when deciding freshness, not local receipt or retry time. |
| `event_id` survives retries; QoS 1 may repeat events | The future station controller must decide whether an event was already handled. |
| `station_id` must match the topic | Validate incoming messages before extracting display text. |
| Detection messages have retain disabled | On startup there may be no detection; the station needs an explicit empty state. |

## Decisions still needed for #22

1. Elena and the consumers need to agree the maximum age for a recent detection.
   The contract has no `expires_at` or shared TTL. The LCD's 20-second inactivity
   timeout is a separate interaction requirement, not a detection expiry rule.
2. Define and review the ES/EU/EN catalogue, its format and fallback for a missing
   translation. Do not infer common names from the scientific identifier.
3. Agree what to show for no detection, expired data, unavailable MQTT and several
   candidate species. David's candidate publication policy is still provisional.
4. Confirm physical character support and pagination controls on the actual LCD.

An existing interface note promises detections with explicit expiry. The current
schema supplies observation timestamps but no expiry duration: the agreement
above is still necessary before calling that interface complete. These decisions
do not block the text formatter or require adding fields to the MQTT schema now.

## Reproduce

In a development environment installed with `python -m pip install -e ".[dev]"`:

```bash
python -m pytest tests/test_lcd_contracts.py -q
```

The eight compatibility cases use synthetic fixtures only, in memory, without
network access, a broker, GPIO or an LCD. Hardware and complete station behaviour
remain outside this review.
