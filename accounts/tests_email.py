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
