"""UPS measurements and diagnostics."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from .entity import GuardianEntity

FIELDS = [('battery_percentage', 'Battery', SensorDeviceClass.BATTERY, '%')]
for prefix in ('input', 'output', 'battery'):
    for suffix, dc, unit in [('voltage', SensorDeviceClass.VOLTAGE, 'V'),
                             ('current', SensorDeviceClass.CURRENT, 'A'),
                             ('power', SensorDeviceClass.POWER, 'W')]:
        FIELDS.append((f'{prefix}_{suffix}', f'{prefix.title()} {suffix}', dc, unit))
FIELDS += [('power_source', 'Power source', None, None),
           ('firmware', 'Firmware', None, None),
           ('firmware_shutdown_percentage', 'Firmware shutdown threshold', None, '%'),
           ('shutdown_request', 'Firmware shutdown request', None, None),
           ('effective_shutdown_percentage', 'Effective shutdown threshold', None, '%')]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(GuardianSensor(entry.runtime_data, *field) for field in FIELDS)


class GuardianSensor(GuardianEntity, SensorEntity):
    def __init__(self, coordinator, key, name, device_class, unit):
        super().__init__(coordinator, key, name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key in ('firmware', 'firmware_shutdown_percentage', 'shutdown_request', 'effective_shutdown_percentage'):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        if self.key == 'effective_shutdown_percentage':
            return max(self.coordinator.config['shutdown_percentage'],
                       self.coordinator.data['firmware_shutdown_percentage'])
        return self.coordinator.data.get(self.key)
