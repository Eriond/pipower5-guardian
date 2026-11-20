# Protocol provenance

Guardian reads PiPower 5 at address `0x5c`, verifying board ID `2602` before reading telemetry. Its register decoding was developed for this project using these vendor references:

- [SunFounder SPC revision 3581063092fe669e7a5538f4a4dc67e9b766863c](https://github.com/sunfounder/spc/tree/3581063092fe669e7a5538f4a4dc67e9b766863c): register offsets, byte order, signed battery current, device identity and shutdown request values.
- [SunFounder PiPower 5 revision ab90a9499e3be7acc3a2e4a2734082be3ba9013b](https://github.com/sunfounder/pipower5/tree/ab90a9499e3be7acc3a2e4a2734082be3ba9013b): source/input distinction and shutdown behavior.
- [Hardware register table](https://docs.sunfounder.com/projects/pipower5/en/latest/pipower_hat.html#i2c-communication).
- [Shutdown configuration](https://docs.sunfounder.com/projects/pipower5/en/latest/pipower5_software.html#safe-shutdown).

The cited source repositories are GPL-3.0; Guardian retains GPL-3.0-or-later licensing. The vendor retains rights to its upstream work. No vendor bus-scanning code, firmware writer, service or kernel driver is bundled. Guardian only reads registers and requests host shutdown through Home Assistant's Supervisor service.

Some vendor documentation contains older identity/address descriptions. The supported `0x5c`, two-byte big-endian board identity `2602`, and little-endian measurement fields were verified on PiPower firmware 2.0.9. Unexpected identities are rejected, not guessed.
