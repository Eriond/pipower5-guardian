# Validation

## Automated checks

35 hardware-free regression tests cover register decoding and malformed responses; mandatory thresholds and firmware emergencies; notification failure isolation; shutdown retry and single-flight behavior; blocked I²C reads; bounded queues; entity-independent polling; and shutdown/unload cleanup. Tests use explicit fake Home Assistant services, not a full HA test harness.

## Live commissioning — 20 November 2026

Tested with Raspberry Pi 5, HAOS 18.5, Core 2026.11.2, Python 3.14.10 and PiPower 5 firmware 2.0.9:

- Configuration/options flows, all 18 entities, polling and reload.
- External-power loss/restoration and notification delivery.
- Low-battery warning and final shutdown notification.
- Automatic threshold shutdown at a temporary 90% threshold: Core exited cleanly, host shutdown proceeded, UPS output and Pi indicators went out.
- Automatic startup on external-power restoration without pressing a button.
- Normal 30% warning / 20% shutdown restored; healthy polling and charging after recovery.
- No undervoltage flags or storage-corruption errors in the collected logs.

A one-shot shutdown listener cleanup error found during commissioning was corrected and covered by a regression test. It did not recur during the subsequent actual shutdown test.

These results cover one hardware installation. Depletion to 20%, prolonged outages, all firmware variants and operation during a stalled Core were not validated. The 1.0.0 release changes metadata, documentation and the default example notification script; the commissioned protection logic is unchanged.
