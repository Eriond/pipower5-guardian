"""UI setup and thresholds. Battery shutdown is mandatory."""
import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, NAME, DEFAULTS, validate


def schema(values, include_bus=True):
    fields = {}
    if include_bus:
        fields[vol.Required('bus', default=values['bus'])] = vol.In([1, 2])
    fields.update({
        vol.Required('shutdown_percentage', default=values['shutdown_percentage']):
            vol.All(vol.Coerce(int), vol.Range(min=15, max=90)),
        vol.Required('warning_percentage', default=values['warning_percentage']):
            vol.All(vol.Coerce(int), vol.Range(min=16, max=100)),
        vol.Required('notification_script', default=values['notification_script']):
            selector.EntitySelector(selector.EntitySelectorConfig(domain='script')),
    })
    return vol.Schema(fields)


class GuardianConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if not self.hass.services.has_service('hassio', 'host_shutdown'):
            return self.async_abort(reason='supervisor_required')
        errors = {}
        if user_input is not None:
            try:
                data = validate(user_input)
            except ValueError:
                errors['base'] = 'invalid_thresholds'
            else:
                await self.async_set_unique_id(f"i2c_{data['bus']}_5c")
                self._abort_if_unique_id_configured()
                # The first setup refresh checks the identity and permissions.
                # A missing board remains visibly not-ready; never a healthy UPS.
                return self.async_create_entry(title=NAME, data=data)
        return self.async_show_form(step_id='user', data_schema=schema({**DEFAULTS, **(user_input or {})}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GuardianOptionsFlow()


class GuardianOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                validate({**values, **user_input})
            except ValueError:
                errors['base'] = 'invalid_thresholds'
            else:
                return self.async_create_entry(title='', data=user_input)
        return self.async_show_form(step_id='init', data_schema=schema({**values, **(user_input or {})}, False), errors=errors)
