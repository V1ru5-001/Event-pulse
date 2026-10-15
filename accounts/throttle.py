"""
Database-backed rate limiting for the sign-in pages.

Vercel functions share no memory, so counters live in the AuthThrottle table.
Each rule counts events for one identifier (an IP, an email, or both) in a
fixed window; reaching the limit locks that identifier out for a while.
"""
import hashlib
import ipaddress
import random
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone

from .models import AuthThrottle


@dataclass(frozen=True)
class Rule:
    limit: int
    window: timedelta
    lockout: timedelta


RULES = {
    # Login: 5 failed attempts for one account from one IP → 15-minute lockout.
    'login':           Rule(5,  timedelta(minutes=15), timedelta(minutes=15)),
    # …and a wider net for one IP trying many different accounts.
    'login_ip':        Rule(30, timedelta(minutes=15), timedelta(minutes=15)),
    'register_ip':     Rule(10, timedelta(hours=1),    timedelta(hours=1)),
    'otp_verify_ip':   Rule(30, timedelta(minutes=15), timedelta(minutes=15)),
    'otp_verify_user': Rule(15, timedelta(hours=1),    timedelta(hours=1)),
    'otp_resend_ip':   Rule(10, timedelta(hours=1),    timedelta(hours=1)),
    'otp_resend_user': Rule(5,  timedelta(hours=1),    timedelta(hours=1)),
    'reset_ip':        Rule(5,  timedelta(hours=1),    timedelta(hours=1)),
    'reset_email':     Rule(3,  timedelta(hours=1),    timedelta(hours=1)),
}


def client_ip(request):
    """
    The visitor's IP. On Vercel every request reaches Django from 127.0.0.1,
    and Vercel overwrites X-Forwarded-For with the real client IP (it does not
    pass on a client-supplied value), so that header is trusted there and only
    there. Elsewhere REMOTE_ADDR is used and the header is ignored.
    """
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def _key(rule_name, ident):
    return hashlib.sha256(f'{rule_name}:{str(ident).strip().lower()}'.encode()).hexdigest()


def seconds_locked(*checks):
    """Longest remaining lockout among (rule_name, identifier) pairs; 0 if none."""
    now = timezone.now()
    keys = [_key(rule, ident) for rule, ident in checks]
    longest = 0
    for until in AuthThrottle.objects.filter(key__in=keys, locked_until__gt=now).values_list('locked_until', flat=True):
        longest = max(longest, int((until - now).total_seconds()) + 1)
    return longest


def hit(rule_name, ident):
    """Count one event. Returns True if this event locked the identifier out."""
    rule, key, now = RULES[rule_name], _key(rule_name, ident), timezone.now()
    for _ in range(2):  # retry once if two requests create the same row at the same moment
        try:
            with transaction.atomic():
                row, _ = AuthThrottle.objects.select_for_update().get_or_create(
                    key=key, defaults={'window_start': now})
                if now >= row.window_start + rule.window or (row.locked_until and now >= row.locked_until):
                    row.count, row.window_start, row.locked_until = 0, now, None
                row.count += 1
                locked = row.count >= rule.limit
                if locked:
                    row.locked_until = now + rule.lockout
                row.save()
            break
        except IntegrityError:
            continue
    else:
        return False
    if random.random() < 0.01:
        _prune(now)
    return locked


def clear(rule_name, ident):
    AuthThrottle.objects.filter(key=_key(rule_name, ident)).delete()


def _prune(now):
    """Drop counters that have long since expired so the table stays small."""
    AuthThrottle.objects.filter(window_start__lt=now - timedelta(days=1)) \
        .exclude(locked_until__gt=now).delete()


def locked_response(request, seconds):
    """Friendly 'slow down' page in the EventPulse design (HTTP 429)."""
    minutes = max(1, (seconds + 59) // 60)
    if minutes >= 60:
        hours = (minutes + 59) // 60
        wait = f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        wait = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return render(request, 'accounts/rate_limited.html', {'wait': wait}, status=429)
