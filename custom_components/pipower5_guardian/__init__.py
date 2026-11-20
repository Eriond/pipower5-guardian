"""Direct I2C UPS integration for Home Assistant OS."""
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN, validate
from .coordinator import GuardianCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    if not hass.services.has_service('hassio', 'host_shutdown'):
        raise ConfigEntryNotReady('Supervisor host_shutdown service is required for mandatory protection')
    config = validate({**entry.data, **entry.options})
    # Retain a timed-out executor future across reloads to avoid thread buildup.
    readers = hass.data.setdefault(DOMAIN, {})
    previous = readers.get(entry.entry_id)
    if previous is not None and previous.pending is not None and not previous.pending.done():
        raise ConfigEntryNotReady('Previous I2C read is still blocked; reload cannot start another')
    coordinator = GuardianCoordinator(hass, entry, config)
    readers[entry.entry_id] = coordinator.reader
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.close()
        raise
    coordinator.start()
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.close()
        return True
    return False
