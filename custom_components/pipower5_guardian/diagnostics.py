"""Only configuration and UPS readings; no credentials."""
async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return {'configuration': c.config, 'sample': c.data,
            'last_update_success': c.last_update_success,
            'shutdown_accepted': c.shutdown.accepted,
            'shutdown_in_progress': c.shutdown.in_progress,
            'i2c_read_pending': c.reader.pending is not None,
            'polling_active': not c.closed}
