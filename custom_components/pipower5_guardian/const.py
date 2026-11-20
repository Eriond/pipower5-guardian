"""Guardian configuration; shutdown cannot be switched off."""
DOMAIN = 'pipower5_guardian'
NAME = 'PiPower 5 Guardian'
VERSION = '1.0.0'
POLL_SECONDS = 5
DEFAULTS = {'bus': 1, 'shutdown_percentage': 20, 'warning_percentage': 30,
            'notification_script': 'script.ups_notify'}


def validate(config):
    """Reject invalid thresholds rather than silently disabling protection."""
    result = {**DEFAULTS, **config}
    if type(result['bus']) is not int or result['bus'] not in (1, 2):
        raise ValueError('Invalid I2C bus')
    shutdown, warning = result['shutdown_percentage'], result['warning_percentage']
    if type(shutdown) is not int or not 15 <= shutdown <= 90:
        raise ValueError('Shutdown threshold must be 15–90%')
    if type(warning) is not int or not shutdown < warning <= 100:
        raise ValueError('Warning threshold must exceed shutdown threshold')
    script = result['notification_script']
    if not isinstance(script, str) or not script.startswith('script.') or not script[7:]:
        raise ValueError('Choose a notification script')
    return result
