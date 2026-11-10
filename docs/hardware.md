# Hardware: inventory and validation plan

**Nothing is considered available, connected or tested because it appears here.** Documentation review date: 05/11/2026. Before wiring, record the exact part number, manufacturer datasheet, voltage, interface and compatibility with the Pi 5. Do not use a generic pinout from another model.

| Planned component | Function | Connection to verify | Status | Required evidence |
|---|---|---|---|---|
| Raspberry Pi 5 | Capture, inference and control | Power supply, cooling and storage suited to the model | Not verified | OS, power and thermal test |
| Omnidirectional USB microphone | Local audio | USB, format, channels and identifier | Not verified | Ten windows in RAM and disconnection test |
| Grove Base Hat | Peripheral interface | Header, buses and compatible drivers | Not verified | Buses/addresses and real reading |
| Temperature and humidity | Environment | Port and bus depending on the model | Not verified | 30 readings per channel, units and range |
| Barometer | Pressure | Bus, address and unit depending on the model | Not verified | 30 readings and comparison against a reference |
| Light (added to the design) | Illumination | Analogue/digital depending on the model | Not verified | Response in two conditions; lux only with a validated conversion |
| PIR | Presence | GPIO/port, level and stabilisation | Not verified | Ten cycles and false triggers |
| Touch | Interaction | GPIO/port and debounce | Not verified | Ten presses without duplication |
| Grove RGB LCD 16×2 | Bird information | Bus, address, power and characters | Not verified | Two lines, colours, switch-off and restart |

No pins or addresses are assigned until the models are identified. Disconnect power before modifying wiring and review electrical compatibility. Do not assume that every library for an earlier Raspberry Pi works on the Pi 5.

## Test record

Each report must include date, author, issue/PR, component reference, connection reviewed, OS/library versions, procedure, expected/observed result, samples or photos and limitations. Allowed statuses: pending, available but untested, tested with evidence, blocked. A simulated test is labelled "simulated" and does not satisfy the physical test.

Elena coordinates the inventory and peripherals; Erik validates environmental sensors with her support; David validates audio and Javier coordinates provisioning. The others review and help with wiring and data. If material is missing, record who is responsible for obtaining it, the expected date and the alternative, without closing the issue for having written the procedure.
