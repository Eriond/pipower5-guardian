"""Stable device and entity identities without MQTT."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, NAME


class GuardianEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        identity = f"i2c_{coordinator.config['bus']}_5c"
        self._attr_unique_id = f'{identity}_{key}'
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, identity)},
            name=NAME, manufacturer='SunFounder', model='PiPower 5',
            sw_version=coordinator.data['firmware'])
