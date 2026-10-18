"""
Email verification codes for email/password sign-ups.

An account is unverified while it has an EmailOTP row. Only an HMAC of each
6-digit code is stored; codes expire after 10 minutes, die after 5 wrong
guesses, and can be re-sent once a minute.
"""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .emailing import log_send_failure
from .models import EmailOTP

logger = logging.getLogger(__name__)

CODE_TTL        = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS    = 5

# verify_code() results
OK, WRONG, EXPIRED, LOCKED, NOT_PENDING = 'ok', 'wrong', 'expired', 'locked', 'not_pending'


def _hash(user, code):
    return salted_hmac('accounts.EmailOTP', f'{user.pk}:{code}', algorithm='sha256').hexdigest()


def is_verified(user):
    return not EmailOTP.objects.filter(user=user).exists()


def mark_verified(user):
    EmailOTP.objects.filter(user=user).delete()


def seconds_until_resend(user):
    otp = EmailOTP.objects.filter(user=user).first()
    if not otp:
        return 0
    wait = (otp.sent_at + RESEND_COOLDOWN - timezone.now()).total_seconds()
    return max(0, int(wait + 0.999))


def send_code(user):
    """
    Issue a fresh code and email it, unless one was sent in the last minute.
    Returns (sent, seconds_to_wait). `sent` is False if the cooldown applies
    or the email couldn't be delivered (the latter also returns wait 0).
    """
    with transaction.atomic():
        otp = EmailOTP.objects.select_for_update().filter(user=user).first()
        now = timezone.now()
        if otp and otp.code_hash and now < otp.sent_at + RESEND_COOLDOWN:
            return False, seconds_until_resend(user)

        code = f'{secrets.randbelow(1_000_000):06d}'
        if otp is None:
            otp = EmailOTP(user=user)
        otp.code_hash, otp.sent_at, otp.attempts = _hash(user, code), now, 0
        otp.save()

    minutes = int(CODE_TTL.total_seconds() // 60)
    body = (
        f'Hi {user.first_name or user.username},\n\n'
        f'Your EventPulse verification code is:\n\n'
        f'    {code}\n\n'
        f'It expires in {minutes} minutes. If you didn\'t create an EventPulse account, '
        f'you can ignore this email.\n\n'
        f'— EventPulse\n'
    )
    try:
        send_mail(f'{code} is your EventPulse code', body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as exc:
        # Never log the code itself, or the full address.
        log_send_failure(logger, 'verification email', user.email, exc)
        # Nothing reached the user, so let them retry straight away.
        EmailOTP.objects.filter(pk=otp.pk).update(sent_at=otp.sent_at - RESEND_COOLDOWN)
        return False, 0
    return True, int(RESEND_COOLDOWN.total_seconds())


def verify_code(user, code):
    """Check a submitted code. Returns (result, attempts_left)."""
    code = (code or '').strip()
    with transaction.atomic():
        otp = EmailOTP.objects.select_for_update().filter(user=user).first()
        if otp is None:
            return NOT_PENDING, 0
        if not otp.code_hash:
            return LOCKED, 0
        if timezone.now() > otp.sent_at + CODE_TTL:
            return EXPIRED, 0

        if code.isdigit() and len(code) == 6 and constant_time_compare(otp.code_hash, _hash(user, code)):
            otp.delete()
            return OK, 0

        otp.attempts += 1
        if otp.attempts >= MAX_ATTEMPTS:
            otp.code_hash = ''  # invalidated: a new code has to be requested
            otp.save(update_fields=['attempts', 'code_hash'])
            return LOCKED, 0
        otp.save(update_fields=['attempts'])
        return WRONG, MAX_ATTEMPTS - otp.attempts
