"""
Optional Sentry error tracking. Only switched on when SENTRY_DSN is set.

Privacy defaults: no personal data, no request bodies, no cookies, no local
variables, and a before_send filter that blanks anything whose name looks
like a password, token, code, OTP, secret or authorization header.
"""
import re

FILTERED = '[Filtered]'

# Field names whose values must never leave the server.
SENSITIVE_KEY = re.compile(r'pass|token|code|otp|secret|authoriz|cookie|session|csrf|api[-_]?key', re.I)

# Password-reset links carry the user id and reset token in the path itself.
RESET_PATH = re.compile(r'(/accounts/password-reset/)[^/?#\s]+/[^/?#\s]+/')


def _scrub_text(value):
    return RESET_PATH.sub(r'\1' + FILTERED + '/' + FILTERED + '/', value) if isinstance(value, str) else value


def _scrub(value):
    """Recursively blank sensitive keys and scrub reset-link paths in strings."""
    if isinstance(value, dict):
        return {k: (FILTERED if isinstance(k, str) and SENSITIVE_KEY.search(k) else _scrub(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return _scrub_text(value)


def scrub_event(event, hint=None):
    request = event.get('request')
    if isinstance(request, dict):
        # Never send bodies or cookies, even if a future setting would allow it.
        request.pop('data', None)
        request.pop('cookies', None)
        if isinstance(request.get('query_string'), str):
            request['query_string'] = re.sub(r'([^&=]+)=([^&]*)',
                                             lambda m: f'{m.group(1)}={FILTERED}' if SENSITIVE_KEY.search(m.group(1)) else m.group(0),
                                             request['query_string'])
    return _scrub(event)


def init_sentry(dsn, environment='production'):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=environment,
        traces_sample_rate=0.05,
        send_default_pii=False,          # no user emails, IPs, cookies or auth headers
        max_request_body_size='never',   # never attach request bodies (forms, passwords, codes)
        include_local_variables=False,   # locals can hold secrets inside ordinary strings
        before_send=scrub_event,
        before_send_transaction=scrub_event,
    )
