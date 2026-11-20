# PiPower 5 Guardian

**Version 1.0.0** — a custom Home Assistant integration for the **SunFounder PiPower 5 UPS**.

Guardian monitors your Raspberry Pi's UPS directly over I²C. It reports battery charge, power source, voltage, current and charging status; notifies your chosen recipients when external power fails or returns; and **gracefully shuts down the whole Home Assistant host when the battery is low**. No MQTT broker, separate app or background daemon is required.

Defaults: **warning at 30%, mandatory shutdown at 20%**. Notifications use a selectable Home Assistant script, so you can add phones or other recipients without changing Guardian.

## Requirements

- Raspberry Pi with **Home Assistant OS and Supervisor**, Core **2026.11.0 or later**. Home Assistant Container/Core without Supervisor is not supported.
- SunFounder **PiPower 5**, a compatible two-cell battery, and a suitable external power supply.
- I²C enabled on the host, with `/dev/i2c-1` (or bus 2) accessible inside the Home Assistant Core container. Guardian does not enable I²C or change host permissions for you. Missing bus access must be resolved before continuing.
- A notification script accepting `title` and `message` variables; see the example below.

For Raspberry Pi 5, verify the **SDSIG jumper connects the centre pin to PI3V3**, enable the Pi bootloader's **`POWER_OFF_ON_HALT=1`**, and enable the board's **default-on jumper** if you want automatic restart when external power returns. Configure hardware only with appropriate power isolation. Guardian does not modify the bootloader or board firmware.

See SunFounder's [hardware guide](https://docs.sunfounder.com/projects/pipower5/en/latest/pipower_hat.html) and [shutdown setup](https://docs.sunfounder.com/projects/pipower5/en/latest/pipower5_software.html#power-off-after-raspberry-pi-shutdown). Its `raspi-config` instructions are for Raspberry Pi OS, not HAOS; HAOS bootloader configuration requires its host administration tools. Preserve existing boot settings when enabling full power-off.

## Download and install

1. Make a Home Assistant backup and keep its recovery key available.
2. Open [Releases](https://github.com/Eriond/pipower5-guardian/releases/latest) and download **`pipower5-guardian-1.0.0.zip`** under **Assets**. This is the installable integration package; you do not need SunFounder's Linux service or the earlier Guardian MQTT app.
3. Extract the ZIP on your computer. Copy its `custom_components/pipower5_guardian` folder into your HA configuration directory, using Samba, SFTP, or your preferred file editor. The result must be:

   ```text
   /config/custom_components/pipower5_guardian/manifest.json
   /config/custom_components/pipower5_guardian/__init__.py
   /config/custom_components/pipower5_guardian/brand/icon.png
   ...
   ```

   Do not nest another `custom_components` folder inside that path. When upgrading, back up the old integration folder before replacing it.
4. Create or select the shared notification script described below.
5. Restart Home Assistant Core, then open **Settings → Devices & services → Add integration → PiPower 5 Guardian**. Refresh the browser if it does not appear immediately.
6. Choose the I²C bus, notification script and thresholds. The `smbus2` dependency is installed automatically.
7. Check that all readings are plausible and the integration is loaded. Saving the setup activates protection immediately; a battery already below the threshold can trigger host shutdown.

Alternatively, download GitHub's source ZIP and copy only `custom_components/pipower5_guardian` from it. Do not copy tests or documentation into the integration folder.

## Shared notification script

Create a script in **Settings → Automations & scenes → Scripts**, switch its editor to YAML, and use this example. Replace `notify.your_phone` with a real notification **entity** supporting `notify.send_message`. This is an example, not an automatically created entity.

```yaml
alias: UPS notifications
mode: queued
max: 10
fields:
  title:
    selector:
      text:
  message:
    required: true
    selector:
      text:
        multiline: true
sequence:
  - variables:
      # Add further notification entities here.
      recipients:
        - notify.your_phone
  - repeat:
      for_each: "{{ recipients }}"
      sequence:
        - action: notify.send_message
          continue_on_error: true
          target:
            entity_id: "{{ repeat.item }}"
          data:
            title: "{{ title | default('PiPower 5 Guardian', true) }}"
            message: "{{ message }}"
```

Select the saved script in Guardian's configuration. Its entity ID need not be `script.ups_notify`. If your notification provider exposes only a service such as `notify.mobile_app_*`, use that provider's action inside your script instead. Guardian only requires the two input variables.

Guardian also creates persistent HA notifications. Remote notifications need working network connectivity during the outage. A failed notification does **not** prevent mandatory shutdown.

## Operation and testing

- Eighteen entities report battery, input/output measurements and diagnostics. Use the device's **External power connected** and **Battery** entities on a dashboard; resolve their actual entity IDs in your installation.
- Polling runs every five seconds, independently of enabled sensor entities. Two consecutive valid critical readings trigger `hassio.host_shutdown`.
- Configure thresholds through the integration's **Configure** action. Shutdown accepts 15–90%; warning must be higher, up to 100%. A higher firmware threshold takes precedence. Firmware low-battery/low-voltage requests also trigger shutdown.
- The board's power-button shutdown request is not handled by this release. Do not rely on it as a Guardian shutdown control.
- First test a short external-power interruption, confirm HA stays available and both power-loss/restoration notifications arrive.
- For a supervised shutdown test, temporarily raise the shutdown threshold above the current charge (within 15–90%) and choose a higher warning threshold. Disconnect only external power, observe the final notification and clean host shutdown, then confirm the UPS cuts output. Restore external power and verify restart. **Restore normal thresholds afterwards.** Do not drain the battery to its hardware cutoff as a test.

Guardian needs a functioning HA Core. Disabling the integration, safe mode or stopping/stalling Core stops its protection. Battery health, load and shutdown duration determine the required reserve; no UPS software can guarantee filesystem integrity under every hardware fault.

## Validation

Commissioned on Raspberry Pi 5, HAOS 18.5, Core 2026.11.2 and PiPower firmware 2.0.9: external-power loss/restoration, notifications, threshold-triggered host shutdown, physical output cutoff and automatic restart were verified. The shutdown test used a temporary **90%** threshold; full discharge to the normal 20% threshold was not tested.

The release retains that tested runtime behavior; 1.0.0 updates release metadata and replaces the original installation-specific default script name with a generic example. Existing configured notification scripts are unchanged.

Run the hardware-free regression suite with Python 3.11 or later:

```sh
python -m unittest discover -s tests -v
```

These tests use fake I²C and HA services and cannot shut down a real host. See [VALIDATION.md](VALIDATION.md) and [protocol provenance](PROTOCOL-SOURCES.md).

## License

Software: **GPL-3.0-or-later**, see [LICENSE](LICENSE). You may use, modify and redistribute it, including commercially, subject to that license. Distributed derivatives must preserve its source-availability and licensing requirements.

The SunFounder name and supplied logo identify the supported hardware. They are third-party branding, excluded from Guardian's software licensing grant; no endorsement is claimed. Dependencies retain their respective licenses. See [NOTICE.md](NOTICE.md).
