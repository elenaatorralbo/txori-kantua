# Audio and data privacy

## Design principle

Local capture and inference on the Raspberry Pi. **Recordings of conversations are not stored and raw audio is not transmitted.** This is a constraint to be implemented and verified, not an already validated guarantee of non-existent software. There is no speaker recognition or transcription.

## Allowed flow

Microphone → bounded window in RAM → inference → species/confidence/time metadata → removal of the reference to the window. The buffer is reused and its size is bounded; secure physical erasure of managed memory is not promised. There will be no temporary WAV files, audio spool, dumps or sample logging.

The provisioning test will review swap and dumps to prevent pages containing audio from reaching disk: disable persistent swap and core dumps for capture/inference, check external libraries and services, or demonstrate equivalent protection. Do not assume that "using RAM" is enough. The policies will be tested with synthetic sound and without recording people in order to verify privacy.

## Allowed data and minimisation

Candidate species, score, model version, observation/reception time, logical station, environmental values and technical health. An approximate location for filtering may remain in local configuration; do not publish sensitive wildlife coordinates. Do not store voices, transcriptions, visitor identifiers or personal presence histories. PIR/touch trigger interaction, not profiles of people.

Retention proposed in ADR 007, pending capacity and team review. Purge and backup only of the necessary metadata. Credentials outside Git, rotated logs, minimal permissions and local access by default. A visible notice at the station will explain that it analyses sounds locally to detect birds and does not keep audio.

## Mandatory verification

1. Inventory every write path, temporary file, log, library cache, swap and dump.
2. Run capture/inference with authorised synthetic sound; review the files created and the data persisted.
3. Inspect MQTT publications and outgoing traffic in a test environment: only allowed metadata.
4. Force disconnection, a full queue and an inference failure; check that no emergency recording mechanism appears.
5. Attach results and configuration to the issue, without personal audio. Repeat before MVP acceptance.

An authorised public corpus without voices can be used as an external evaluation fixture, with origin and licence recorded; this is not equivalent to keeping audio captured by the station. In case of accidental persistence or transmission, stop capture, limit access, delete the affected data according to the team procedure, fix and repeat the tests before restarting.
