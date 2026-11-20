"""Pure policy: two consecutive valid samples; no optional shutdown mode."""
from dataclasses import dataclass


@dataclass
class Decision:
    notifications: tuple[str, ...] = ()
    shutdown_reason: str | None = None


class Policy:
    def __init__(self, shutdown=20, warning=30):
        self.shutdown = shutdown
        self.warning = warning
        self.last_time = None
        self.battery = None
        self.warned = False
        self.critical_count = 0

    def invalid(self):
        self.last_time = None
        self.critical_count = 0

    def evaluate(self, data, now):
        if self.last_time is None or now - self.last_time > 12:
            self.critical_count = 0
        self.last_time = now
        battery = data['power_source'] == 'battery'
        messages = []
        if battery and self.battery is not True:
            messages.append('External power is lost or insufficient; PiPower 5 is powering the server from its battery.')
        elif not battery and self.battery is True:
            messages.append('External power has been restored.')
        self.battery = battery
        effective = max(self.shutdown, data['firmware_shutdown_percentage'])
        if battery and data['battery_percentage'] <= max(self.warning, effective):
            if not self.warned:
                messages.append(f"UPS battery is low ({data['battery_percentage']}%). Graceful shutdown threshold: {effective}%.")
                self.warned = True
        elif not battery or data['battery_percentage'] > self.warning + 5:
            self.warned = False
        # Respect emergency battery/voltage requests even when source reporting
        # lags. Button request 2 is not a battery safety signal and is ignored.
        emergency = data['shutdown_request'] in (1, 3)
        critical = emergency or (battery and data['battery_percentage'] <= effective)
        self.critical_count = self.critical_count + 1 if critical else 0
        reason = None
        if self.critical_count >= 2:
            reason = ('PiPower firmware requests battery protection shutdown' if emergency
                      else f"Battery reached {data['battery_percentage']}% (threshold {effective}%)")
        return Decision(tuple(messages), reason)
