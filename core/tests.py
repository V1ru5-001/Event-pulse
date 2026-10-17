import os
import tempfile
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import include, path

from .storage import ForgivingStaticFilesStorage


def _forbidden(request):
    raise PermissionDenied


def _broken(request):
    raise RuntimeError('boom')


# The real site plus two views that fail on purpose.
urlpatterns = [
    path('__test__/forbidden/', _forbidden),
    path('__test__/broken/', _broken),
    path('', include('core.urls')),
]

TEST_SETTINGS = dict(
    DEBUG=False,
    ROOT_URLCONF='core.tests',
    SECURE_SSL_REDIRECT=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)


@override_settings(**TEST_SETTINGS)
class ErrorPageTests(TestCase):

    def test_404_uses_our_page(self):
        r = self.client.get('/no-such-page/')
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "That page doesn't exist.", status_code=404)
        self.assertContains(r, 'class="epx"', status_code=404)
        self.assertContains(r, 'href="/"', status_code=404)  # signed out → landing page

    def test_404_signed_in_points_to_feed(self):
        user = get_user_model().objects.create_user(username='ada', email='ada@example.com', password='x')
        self.client.force_login(user)
        r = self.client.get('/no-such-page/')
        self.assertContains(r, 'href="/home/"', status_code=404)
        self.assertContains(r, 'Back to your feed', status_code=404)

    def test_missing_object_404_uses_our_page(self):
        r = self.client.get('/accounts/profile/nobody-here/')
        self.assertContains(r, "That page doesn't exist.", status_code=404)

    def test_403_uses_our_page(self):
        r = self.client.get('/__test__/forbidden/')
        self.assertContains(r, "You can't open this.", status_code=403)

    def test_500_uses_our_page(self):
        r = Client(raise_request_exception=False).get('/__test__/broken/')
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, 'Something broke on our side.', status_code=500)
        self.assertContains(r, "We've been notified, try again in a minute.", status_code=500)

    def test_500_page_has_no_template_logic(self):
        with open(os.path.join(settings.BASE_DIR, 'templates', '500.html'), encoding='utf-8') as f:
            source = f.read()
        for tag in ('{%', '{{', '{#'):
            self.assertNotIn(tag, source)

    def test_500_page_survives_a_broken_database_and_context_processors(self):
        # If the error came from the database, the 500 page must not need it.
        with mock.patch('social.context_processors.unread_messages', side_effect=RuntimeError('db down')), \
                mock.patch('django.db.backends.utils.CursorWrapper.execute', side_effect=RuntimeError('db down')):
            r = Client(raise_request_exception=False).get('/__test__/broken/')
        self.assertContains(r, 'Something broke on our side.', status_code=500)

    def test_stale_form_on_other_pages_gets_designed_403(self):
        event_post = Client(enforce_csrf_checks=True).post('/events/anything/rsvp/', {})
        self.assertContains(event_post, 'This page expired.', status_code=403)


class MissingStaticFileTests(TestCase):

    def test_missing_static_file_links_plainly_instead_of_crashing(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, 'css'))
        with open(os.path.join(root, 'css', 'real.css'), 'w') as f:
            f.write('body{}')
        with override_settings(STATIC_ROOT=root, STATIC_URL='/static/'):
            storage = ForgivingStaticFilesStorage()
            with self.assertLogs('core.storage', level='WARNING'):
                self.assertEqual(storage.url('css/missing.css'), '/static/css/missing.css')
            self.assertTrue(storage.url('css/real.css').startswith('/static/css/real.'))

    def test_settings_use_the_forgiving_storage(self):
        self.assertEqual(settings.STORAGES['staticfiles']['BACKEND'], 'core.storage.ForgivingStaticFilesStorage')

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_missing_media_file_is_a_quiet_404(self):
        with override_settings(USE_S3=False):
            r = self.client.get('/media/profiles/does-not-exist.png')
        self.assertEqual(r.status_code, 404)


class SentryTests(TestCase):

    def test_off_without_a_dsn(self):
        import sentry_sdk
        self.assertEqual(settings.SENTRY_DSN, '')
        self.assertFalse(sentry_sdk.get_client().is_active())

    def test_init_uses_privacy_safe_options(self):
        from . import sentry
        with mock.patch('sentry_sdk.init') as init:
            sentry.init_sentry('https://public@example.ingest.sentry.io/1', environment='staging')
        kwargs = init.call_args.kwargs
        self.assertEqual(kwargs['environment'], 'staging')
        self.assertEqual(kwargs['traces_sample_rate'], 0.05)
        self.assertIs(kwargs['send_default_pii'], False)
        self.assertEqual(kwargs['max_request_body_size'], 'never')
        self.assertIs(kwargs['include_local_variables'], False)
        self.assertIs(kwargs['before_send'], sentry.scrub_event)
        self.assertIs(kwargs['before_send_transaction'], sentry.scrub_event)

    def test_scrubber_removes_secrets_and_keeps_the_rest(self):
        from .sentry import FILTERED, scrub_event
        event = {
            'request': {
                'url': 'https://event-pulse-dun.vercel.app/accounts/password-reset/MQ/cx7-abc123/',
                'query_string': 'next=/home/&token=abc&otp=123456',
                'data': {'password': 'hunter2', 'code': '123456'},
                'cookies': {'sessionid': 'xyz'},
                'headers': {'Authorization': 'Bearer abc', 'X-Csrftoken': 'abc', 'User-Agent': 'Firefox'},
            },
            'extra': {'new_password1': 'p', 'otp_code': '1', 'client_secret': 's', 'event_title': 'Gig Night',
                      'nested': [{'access_token': 't', 'count': 3}]},
            'transaction': '/accounts/password-reset/MQ/set-password/',
        }
        out = scrub_event(event)
        req = out['request']
        self.assertNotIn('data', req)
        self.assertNotIn('cookies', req)
        self.assertEqual(req['url'], f'https://event-pulse-dun.vercel.app/accounts/password-reset/{FILTERED}/{FILTERED}/')
        self.assertEqual(req['query_string'], f'next=/home/&token={FILTERED}&otp={FILTERED}')
        self.assertEqual(req['headers']['Authorization'], FILTERED)
        self.assertEqual(req['headers']['X-Csrftoken'], FILTERED)
        self.assertEqual(req['headers']['User-Agent'], 'Firefox')
        for key in ('new_password1', 'otp_code', 'client_secret'):
            self.assertEqual(out['extra'][key], FILTERED, key)
        self.assertEqual(out['extra']['event_title'], 'Gig Night')
        self.assertEqual(out['extra']['nested'], [{'access_token': FILTERED, 'count': 3}])
        self.assertEqual(out['transaction'], f'/accounts/password-reset/{FILTERED}/{FILTERED}/')
