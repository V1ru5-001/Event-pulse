"""Helpers for reporting email delivery problems without leaking addresses or secrets."""


def mask_email(address):
    """'alice@gmail.com' -> 'a***@gmail.com'."""
    name, at, domain = (address or '').partition('@')
    if not at:
        return '***'
    return f'{name[:1]}***@{domain}'


def log_send_failure(logger, what, address, exc):
    """One ERROR line (shows in Vercel logs): what failed, for whom (masked) and why."""
    logger.error('Could not send %s to %s: %s: %s', what, mask_email(address), type(exc).__name__, exc)
