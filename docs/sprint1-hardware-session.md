# Sprint 1 — hardware validation session

Preparation for Elena's issues [#1](https://github.com/elenaatorralbo/txori-kantua/issues/1), [#3](https://github.com/elenaatorralbo/txori-kantua/issues/3), [#5](https://github.com/elenaatorralbo/txori-kantua/issues/5) and [#6](https://github.com/elenaatorralbo/txori-kantua/issues/6).
This is a procedure, not evidence that tests ran. Elena reports that the sensors
work; the session records the exact setup and checks the outstanding criteria.

## Before the session

Prepare the Pi, its current storage, power supply, cooling, Grove components,
USB microphone and a camera. Keep the working scripts already on the Pi.
Do not reflash or overwrite a working installation just to collect evidence.
Have another member available to review the wiring and later the reports.

Copy the four templates below to the evidence directory with the actual date.
The templates are outside that directory so blank forms are not mistaken for
completed reports. After copying, replace the procedure link in each report
with the path to the session guide and record the exact commands you ran.

| Issue | Template | Output needed |
|---|---|---|
| #1 | [Inventory](templates/issue-1-inventory.md) | Models, availability, wiring review, missing-component decisions |
| #3 | [Grove](templates/issue-3-grove.md) | Bus/address record, versioned driver and real reading |
| #5 | [PIR and touch](templates/issue-5-inputs.md) | Ten real cycles per input, timing, false triggers and disconnect behaviour |
| #6 | [LCD](templates/issue-6-lcd.md) | Display photos/video, text policy, backlight and restart results |

## 1. Preserve and identify the working setup

Photograph the current connections before changing anything. Identify model and
revision markings and find the matching manufacturer's documentation. Record
ports, buses, addresses, electrical levels and power requirements from that
specific model; mark unknown values PENDING rather than guessing them.
Power off before changing connections. Have the wiring checked for voltage
compatibility and bus/address conflicts before reconnecting power.

For the software baseline, run these read-only commands from the repository:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
git rev-parse HEAD
git status --short
cat /etc/os-release
uname -m
python3 --version
```

Also record the interpreter and driver versions used by the working sensor
script, which may differ from the default Python. Record its path and exact
invocation; include the script in the PR if it is not already versioned.
Follow [provisioning.md](provisioning.md) with Javier if the environment is not
ready. This session does not establish that #2 is complete.

## 2. Grove buses and one real reading

Complete #1 first and verify that the Pi environment is usable. Record the
exact Hat model and compatible driver. List the enabled buses and the observed
addresses using the model's documented diagnostics. If available, `i2cdetect -l`
lists I2C adapters; it is not evidence of detected device addresses. Select any
address-probing procedure only after identifying the devices and bus; do not
copy a scan command or bus number from another model.

Run the existing minimal reading script. Record the command, driver version,
port/address, timestamp, value and unit. Compare the observation with its
expected behaviour. A bus listing alone does not satisfy the real-reading
criterion. Record any incompatibility, attempted fix and verified alternative.

## 3. PIR and touch

Record active levels and measured stabilization time. Use the current hardware
adapter to capture raw levels, logical states and generated actions with UTC
session time plus elapsed monotonic milliseconds. Do not treat terminal mock
samples as physical observations.

For PIR, start after recording warmup, then perform ten presence/absence cycles.
Check that sustained presence does not repeatedly generate activation actions.
For touch, perform ten press/release cycles, including a held press; check that
one press produces one action. Record the chosen debounce interval and how it
was selected. Observe false triggers and note the observation duration.

Record disconnect behaviour through a controlled power-off/disconnect/restart
procedure unless the exact device documentation explicitly permits another
method. A GPIO level alone may not reveal a disconnected sensor; record that
limitation rather than claiming automatic failure detection.

Software reference: [PR #43](https://github.com/elenaatorralbo/txori-kantua/pull/43)
contains logical PIR/touch handlers and synthetic tests. Use the reviewed,
merged version when available; otherwise record the exact PR commit tested.
These handlers still need an adapter for the identified hardware.

## 4. LCD

Use the working LCD driver to write each row and control the backlight. Record
the exact command or script for every test. Software reference:
[PR #42](https://github.com/elenaatorralbo/txori-kantua/pull/42) contains the text
formatter, not the physical driver. Its terminal preview is not LCD evidence.

Test two full rows, a long name spanning pages, an accented name using the
chosen character policy, colours and backlight off. Then write a shorter name
after a longer one and check that no old characters remain. Restart the test
process and verify that output recovers. Record separately any power-cycle test.

## Finish

Complete each report with expected and observed results, photo/log links,
limitations and reviewer. Follow [evidence rules](evidence/README.md): review
attachments for credentials, network details or people before committing.
Open a PR referencing the relevant issues. Close an issue only after its
criteria, review and integration are complete; record a blocker and next action
for any untested or failed criterion. The 20-second interaction timeout belongs
to #22 and is not required to finish #6's basic display validation.
