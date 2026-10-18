"""Small helpers for reading settings from environment variables."""
import os

_QUOTES = ('"', "'")


def env_str(name, default=''):
    """
    The variable's value with surrounding whitespace (including a trailing
    newline) and one pair of matching surrounding quotes removed. Pasted
    secrets often carry these by accident.
    """
    value = os.environ.get(name, default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTES:
        value = value[1:-1].strip()
    return value


def env_bool(name, default=False):
    """True for True/true/1/yes/on, False for anything else; `default` when unset."""
    value = env_str(name)
    if not value:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')
