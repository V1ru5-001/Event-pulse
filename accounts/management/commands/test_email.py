"""
Check the email settings step by step and send one test message.

    python manage.py test_email you@example.com

Prints the active settings (never the password itself), then connects to the
SMTP server one step at a time so a failure shows exactly where it happened
and what the server said.
"""
import os
import smtplib
import socket
import ssl

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


def describe_secret(raw):
    """Facts about a secret that help debugging without revealing it."""
    if raw is None:
        return 'not set'
    stripped = raw.strip()
    facts = [f'{len(raw)} characters as stored']
    if raw != stripped:
        facts.append('has leading/trailing whitespace or a newline (trimmed by settings)')
    if stripped[:1] in ('"', "'") or stripped[-1:] in ('"', "'"):
        facts.append('starts or ends with a quote (trimmed by settings)')
    if ' ' in stripped.strip('"\'').strip():
        facts.append('contains spaces inside it')
    return '; '.join(facts)


class Command(BaseCommand):
    help = 'Show the email settings, test the SMTP login step by step and send a test message.'

    def add_arguments(self, parser):
        parser.add_argument('address', help='Where to send the test message.')

    def line(self, label, value):
        self.stdout.write(f'  {label:<22} {value}')

    def ok(self, step):
        self.stdout.write(self.style.SUCCESS(f'  OK    {step}'))

    def fail(self, step, exc):
        code = getattr(exc, 'smtp_code', None)
        reply = getattr(exc, 'smtp_error', None)
        if isinstance(reply, bytes):
            reply = reply.decode('utf-8', 'replace')
        self.stdout.write(self.style.ERROR(f'  FAIL  {step}'))
        self.stdout.write(f'        exception: {type(exc).__module__}.{type(exc).__name__}')
        if code is not None:
            self.stdout.write(f'        server code: {code}')
        self.stdout.write(f'        server reply: {reply if reply else exc}')
        raise CommandError(f'Stopped at: {step}')

    def handle(self, *args, **options):
        address = options['address']
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or ''

        self.stdout.write(self.style.MIGRATE_HEADING('Email settings in use'))
        self.line('EMAIL_BACKEND', settings.EMAIL_BACKEND)
        self.line('EMAIL_HOST', getattr(settings, 'EMAIL_HOST', '') or '(not set)')
        self.line('EMAIL_PORT', getattr(settings, 'EMAIL_PORT', ''))
        self.line('EMAIL_USE_TLS', getattr(settings, 'EMAIL_USE_TLS', False))
        self.line('EMAIL_USE_SSL', getattr(settings, 'EMAIL_USE_SSL', False))
        self.line('EMAIL_HOST_USER', getattr(settings, 'EMAIL_HOST_USER', '') or '(not set)')
        self.line('EMAIL_HOST_PASSWORD', f'{len(password)} characters after trimming'
                                         + ('; contains spaces' if ' ' in password else '')
                                         + ('; contains quotes' if '"' in password or "'" in password else ''))
        self.line('  raw env value', describe_secret(os.environ.get('EMAIL_HOST_PASSWORD')))
        self.line('DEFAULT_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL)
        self.line('EMAIL_TIMEOUT', getattr(settings, 'EMAIL_TIMEOUT', None))

        if settings.EMAIL_BACKEND != SMTP_BACKEND:
            self.stdout.write(self.style.WARNING(
                '\nNot using SMTP, so no real email is sent. Set EMAIL_HOST (and the other EMAIL_* '
                'variables) to test SMTP. Sending the test message through the current backend anyway:'))
            EmailMessage('EventPulse test email', 'This is a test from manage.py test_email.',
                         settings.DEFAULT_FROM_EMAIL, [address]).send()
            return

        if not getattr(settings, 'EMAIL_HOST', ''):
            raise CommandError(
                'EMAIL_HOST is not set, so there is no mail server configured and every send will fail. '
                'Set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER and EMAIL_HOST_PASSWORD (or set DEBUG=True '
                'locally to print emails to the console instead).')

        host, port = settings.EMAIL_HOST, settings.EMAIL_PORT
        timeout = getattr(settings, 'EMAIL_TIMEOUT', None) or 10
        use_ssl, use_tls = settings.EMAIL_USE_SSL, settings.EMAIL_USE_TLS
        context = ssl.create_default_context()

        self.stdout.write(self.style.MIGRATE_HEADING(f'\nConnecting to {host}:{port}'))
        try:
            server = (smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) if use_ssl
                      else smtplib.SMTP(host, port, timeout=timeout))
        except (OSError, smtplib.SMTPException, socket.timeout) as exc:
            self.fail('connect' + (' (implicit SSL)' if use_ssl else ''), exc)
        self.ok('connect' + (' (implicit SSL)' if use_ssl else ''))

        try:
            try:
                code, reply = server.ehlo()
                if code != 250:
                    raise smtplib.SMTPResponseException(code, reply)
            except (OSError, smtplib.SMTPException) as exc:
                self.fail('EHLO', exc)
            self.ok('EHLO')

            if use_tls:
                try:
                    server.starttls(context=context)
                    server.ehlo()
                except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
                    self.fail('STARTTLS', exc)
                self.ok('STARTTLS')

            if settings.EMAIL_HOST_USER:
                try:
                    server.login(settings.EMAIL_HOST_USER, password)
                except (OSError, smtplib.SMTPException) as exc:
                    self.fail('login (AUTH)', exc)
                self.ok('login (AUTH)')
            else:
                self.stdout.write(self.style.WARNING('  SKIP  login: EMAIL_HOST_USER is not set'))

            message = EmailMessage(
                'EventPulse test email',
                'This is a test from manage.py test_email. If you can read this, sending works.',
                settings.DEFAULT_FROM_EMAIL, [address],
            ).message()
            try:
                refused = server.sendmail(settings.DEFAULT_FROM_EMAIL, [address], message.as_bytes())
            except (OSError, smtplib.SMTPException) as exc:
                self.fail('send', exc)
            if refused:
                self.fail('send', smtplib.SMTPRecipientsRefused(refused))
            self.ok(f'send to {address}')
        finally:
            try:
                server.quit()
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS('\nAll steps passed. Check the inbox (and spam folder).'))
