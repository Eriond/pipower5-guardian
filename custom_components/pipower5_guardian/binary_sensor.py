"""Power presence and charging state."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from .entity import GuardianEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        GuardianBinary(entry.runtime_data, 'input_connected', 'External power connected', BinarySensorDeviceClass.PLUG),
        GuardianBinary(entry.runtime_data, 'charging', 'Charging', BinarySensorDeviceClass.BATTERY_CHARGING),
        GuardianBinary(entry.runtime_data, 'default_on', 'Automatic power-on jumper', None),
    ])


class GuardianBinary(GuardianEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name, device_class):
        super().__init__(coordinator, key, name)
        self._attr_device_class = device_class
        if key == 'default_on':
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return self.coordinator.data.get(self.key)
