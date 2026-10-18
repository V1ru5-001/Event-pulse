import os
import smtplib
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.env import env_bool, env_str

SECRET = 'abcd efgh ijkl mnop'
SMTP = dict(
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    EMAIL_HOST='smtp.gmail.com', EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
    EMAIL_HOST_USER='sender@gmail.com', EMAIL_HOST_PASSWORD=SECRET, EMAIL_TIMEOUT=10,
    DEFAULT_FROM_EMAIL='EventPulse <sender@gmail.com>',
)


class EnvHelperTests(SimpleTestCase):

    def test_env_str_trims_whitespace_newlines_and_quotes(self):
        cases = {'  secret\n': 'secret', '"secret"': 'secret', "'secret'": 'secret',
                 ' "abcd efgh" \r\n': 'abcd efgh', 'sec"ret': 'sec"ret', '"': '"'}
        for raw, expected in cases.items():
            with mock.patch.dict(os.environ, {'X_TEST': raw}):
                self.assertEqual(env_str('X_TEST'), expected, repr(raw))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('X_TEST', None)
            self.assertEqual(env_str('X_TEST', 'fallback'), 'fallback')

    def test_env_bool(self):
        for raw, expected in {'True': True, 'true': True, '1': True, 'yes': True, ' "True" ': True,
                              'False': False, 'false': False, '0': False, 'nope': False}.items():
            with mock.patch.dict(os.environ, {'X_FLAG': raw}):
                self.assertIs(env_bool('X_FLAG'), expected, raw)
        os.environ.pop('X_FLAG', None)
        self.assertIs(env_bool('X_FLAG', True), True)


def run(*args):
    out = StringIO()
    try:
        call_command('test_email', *args, stdout=out)
        error = None
    except CommandError as exc:
        error = exc
    return out.getvalue(), error


@override_settings(**SMTP)
class TestEmailCommandTests(SimpleTestCase):

    def fake_server(self):
        server = mock.MagicMock()
        server.ehlo.return_value = (250, b'smtp.gmail.com at your service')
        server.sendmail.return_value = {}
        return server

    def test_prints_settings_but_never_the_password(self):
        with mock.patch('smtplib.SMTP', return_value=self.fake_server()), \
                mock.patch.dict(os.environ, {'EMAIL_HOST_PASSWORD': f' "{SECRET}"\n'}):
            out, error = run('me@example.com')
        self.assertIsNone(error)
        self.assertNotIn(SECRET, out)
        self.assertNotIn('abcd', out)
        self.assertIn('sender@gmail.com', out)                        # full user, as asked
        self.assertIn('19 characters after trimming; contains spaces', out)
        self.assertIn('trailing whitespace or a newline', out)
        self.assertIn('starts or ends with a quote', out)

    def test_happy_path_runs_each_step_and_sends(self):
        server = self.fake_server()
        with mock.patch('smtplib.SMTP', return_value=server) as smtp:
            out, error = run('me@example.com')
        self.assertIsNone(error)
        smtp.assert_called_once_with('smtp.gmail.com', 587, timeout=10)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with('sender@gmail.com', SECRET)
        self.assertEqual(server.sendmail.call_args.args[1], ['me@example.com'])
        for step in ('OK    connect', 'OK    EHLO', 'OK    STARTTLS', 'OK    login (AUTH)', 'OK    send to me@example.com'):
            self.assertIn(step, out)

    def test_disconnect_during_login_is_reported_with_the_exception(self):
        server = self.fake_server()
        server.login.side_effect = smtplib.SMTPServerDisconnected('Connection unexpectedly closed')
        with mock.patch('smtplib.SMTP', return_value=server):
            out, error = run('me@example.com')
        self.assertIsNotNone(error)
        self.assertIn('FAIL  login (AUTH)', out)
        self.assertIn('smtplib.SMTPServerDisconnected', out)
        self.assertIn('Connection unexpectedly closed', out)
        server.sendmail.assert_not_called()

    def test_bad_credentials_show_the_server_code_and_reply(self):
        server = self.fake_server()
        server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b'5.7.8 Username and Password not accepted. BadCredentials')
        with mock.patch('smtplib.SMTP', return_value=server):
            out, _ = run('me@example.com')
        self.assertIn('smtplib.SMTPAuthenticationError', out)
        self.assertIn('server code: 535', out)
        self.assertIn('BadCredentials', out)

    def test_connect_failure(self):
        with mock.patch('smtplib.SMTP', side_effect=TimeoutError('timed out')):
            out, error = run('me@example.com')
        self.assertIn('FAIL  connect', out)
        self.assertIn('TimeoutError', out)

    @override_settings(EMAIL_PORT=465, EMAIL_USE_TLS=False, EMAIL_USE_SSL=True)
    def test_implicit_ssl_on_465(self):
        server = self.fake_server()
        with mock.patch('smtplib.SMTP_SSL', return_value=server) as smtp_ssl, mock.patch('smtplib.SMTP') as plain:
            out, error = run('me@example.com')
        self.assertIsNone(error)
        plain.assert_not_called()
        self.assertEqual(smtp_ssl.call_args.args, ('smtp.gmail.com', 465))
        server.starttls.assert_not_called()
        self.assertIn('OK    connect (implicit SSL)', out)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_non_smtp_backend_says_so(self):
        out, error = run('me@example.com')
        self.assertIsNone(error)
        self.assertIn('Not using SMTP', out)

    @override_settings(EMAIL_HOST='')
    def test_missing_host_is_explained(self):
        out, error = run('me@example.com')
        self.assertIn('EMAIL_HOST is not set', str(error))


# ═══════════════ Part B: failed sends are visible and don't lock people out ═══════════════

import re  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.core import mail  # noqa: E402
from django.test import TestCase  # noqa: E402

from accounts import throttle  # noqa: E402
from accounts.emailing import mask_email  # noqa: E402
from accounts.models import AuthThrottle  # noqa: E402

BROKEN = mock.patch('django.core.mail.backends.locmem.EmailBackend.send_messages',
                    side_effect=smtplib.SMTPServerDisconnected('Connection unexpectedly closed'))

APP = dict(
    SECURE_SSL_REDIRECT=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    TRUST_X_FORWARDED_FOR=False,
)
SEND_ERROR = "We couldn&#x27;t send email right now. Please try again in a few minutes."


class MaskTests(SimpleTestCase):
    def test_mask_email(self):
        self.assertEqual(mask_email('alice@gmail.com'), 'a***@gmail.com')
        self.assertEqual(mask_email('not-an-email'), '***')
        self.assertEqual(mask_email(''), '***')


@override_settings(**APP)
class ResetSendFailureTests(TestCase):

    def setUp(self):
        get_user_model().objects.create_user(username='alice', email='alice@gmail.com', password='Str0ng!Pass99')

    def reset(self, email):
        return self.client.post('/accounts/password-reset/', {'email': email})

    def test_failed_send_is_shown_and_logged_without_the_full_address(self):
        with BROKEN, self.assertLogs('accounts.forms', 'ERROR') as logs:
            r = self.reset('alice@gmail.com')
        self.assertEqual(r.status_code, 200)              # stays on the form, not "check your email"
        self.assertContains(r, SEND_ERROR)
        line = ' '.join(logs.output)
        self.assertIn('a***@gmail.com', line)
        self.assertIn('SMTPServerDisconnected', line)
        self.assertNotIn('alice@gmail.com', line)

    def test_unknown_address_gets_the_normal_page(self):
        with BROKEN:
            r = self.reset('nobody@example.com')
        self.assertRedirects(r, '/accounts/password-reset/sent/', fetch_redirect_response=False)

    def test_failed_sends_do_not_use_up_the_limits(self):
        with BROKEN, self.assertLogs('accounts.forms', 'ERROR'):
            for _ in range(8):
                self.assertEqual(self.reset('alice@gmail.com').status_code, 200)
        self.assertFalse(AuthThrottle.objects.exists())
        # Once email works again, the person still has their full allowance.
        for _ in range(3):
            self.assertEqual(self.reset('alice@gmail.com').status_code, 302)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(self.reset('alice@gmail.com').status_code, 429)

    def test_unknown_addresses_still_count(self):
        for _ in range(3):
            self.reset('ghost@example.com')
        self.assertEqual(self.reset('ghost@example.com').status_code, 429)

    def test_google_only_notice_failure_is_also_reported(self):
        from allauth.socialaccount.models import SocialAccount
        gina = get_user_model().objects.create_user(username='gina', email='gina@gmail.com', password=None)
        SocialAccount.objects.create(user=gina, provider='google', uid='g-1')
        with BROKEN, self.assertLogs('accounts.forms', 'ERROR'):
            r = self.reset('gina@gmail.com')
        self.assertContains(r, SEND_ERROR)


REGISTER = {'first_name': 'Cara', 'username': 'cara', 'email': 'cara@example.com', 'role': 'guest',
            'password1': 'Str0ng!Pass99', 'password2': 'Str0ng!Pass99', 'terms': 'on'}


@override_settings(**APP)
class CodeSendFailureTests(TestCase):

    def test_register_with_broken_email_says_so_and_keeps_resend_available(self):
        with BROKEN, self.assertLogs('accounts.otp', 'ERROR') as logs:
            self.client.post('/accounts/register/', REGISTER)
        self.assertIn('c***@example.com', ' '.join(logs.output))
        self.assertNotIn('cara@example.com', ' '.join(logs.output))
        page = self.client.get('/accounts/verify-email/')
        self.assertContains(page, "We couldn't send your code")
        self.assertContains(page, 'data-wait="0" >')  # resend button rendered without `disabled`

    def test_failed_resends_do_not_count(self):
        with BROKEN, self.assertLogs('accounts.otp', 'ERROR'):
            self.client.post('/accounts/register/', REGISTER)
            for _ in range(8):
                self.assertEqual(self.client.post('/accounts/verify-email/resend/').status_code, 302)
        user = get_user_model().objects.get(email='cara@example.com')
        resend_keys = [throttle._key('otp_resend_user', user.pk), throttle._key('otp_resend_ip', '127.0.0.1')]
        self.assertFalse(AuthThrottle.objects.filter(key__in=resend_keys).exists())
        # Email works again: the resend goes out and the failure notice disappears.
        r = self.client.post('/accounts/verify-email/resend/', follow=True)
        self.assertContains(r, 'New code sent')
        self.assertNotContains(r, "We couldn't send your code")
        code = re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
        r = self.client.post('/accounts/verify-email/', {'code': code})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)

    def test_wrong_guesses_still_count(self):
        self.client.post('/accounts/register/', REGISTER)
        for _ in range(15):
            self.client.post('/accounts/verify-email/', {'code': 'abcdef'})
        self.assertEqual(self.client.post('/accounts/verify-email/', {'code': 'abcdef'}).status_code, 429)


@override_settings(**APP)
class LockoutPageTests(TestCase):

    def test_429_uses_the_design_with_minutes_and_retry_after(self):
        get_user_model().objects.create_user(username='ada', email='ada@example.com', password='Str0ng!Pass99')
        for _ in range(5):
            r = self.client.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'wrong'})
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "Let's take a breather", status_code=429)
        self.assertContains(r, '15 minutes', status_code=429)
        self.assertNotContains(r, 'Too Many Requests', status_code=429)
        self.assertTrue(880 <= int(r['Retry-After']) <= 901, r['Retry-After'])
