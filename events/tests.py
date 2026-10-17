from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Category, Event

User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class LandingCounterTests(TestCase):

    def make_users(self, n, role):
        for i in range(n):
            User.objects.create_user(username=f'{role}{i}', email=f'{role}{i}@example.com', password='x', role=role)

    def make_events(self, n):
        host = User.objects.create_user(username='host', email='host@example.com', password='x', role='guest')
        for i in range(n):
            Event.objects.create(title=f'Event {i}', description='d', organiser=host, category=Category.objects.first(),
                                 location_name='Hall', start_datetime=timezone.now() + timedelta(days=i + 1),
                                 status='published')

    def test_no_counters_below_ten(self):
        self.make_users(9, 'student')
        self.make_events(9)
        html = self.client.get('/').content.decode()
        self.assertNotIn('epx-lstats', html)
        self.assertNotIn('data-target="0"', html)

    def test_only_counters_at_ten_or_more_are_shown(self):
        self.make_users(12, 'student')
        self.make_users(3, 'society')
        self.make_events(10)
        html = self.client.get('/').content.decode()
        self.assertIn('class="epx-lstats"', html)
        self.assertIn('data-target="12"', html)   # students
        self.assertIn('data-target="10"', html)   # events
        self.assertNotIn('data-target="3"', html)  # societies hidden
        self.assertEqual(html.count('land-stat__num'), 2 + html.count('.land-stat__num'))


LEGAL_SETTINGS = dict(
    SECURE_SSL_REDIRECT=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    SOCIALACCOUNT_PROVIDERS={'google': {'SCOPE': ['profile', 'email'],
                                        'APP': {'client_id': 'test-id', 'secret': 'test-secret', 'key': ''}}},
)


@override_settings(**LEGAL_SETTINGS)
class LegalPageTests(TestCase):

    def test_pages_are_public_and_marked_as_testing(self):
        for path, heading in [('/privacy/', 'Privacy Policy'), ('/terms/', 'Terms of Service')]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertContains(r, heading)
            self.assertContains(r, 'Last updated:')
            self.assertContains(r, 'EventPulse is currently in testing.')
            self.assertContains(r, 'getinformedconcepts@gmail.com')
            self.assertContains(r, 'class="epx"')

    def test_privacy_covers_the_required_points(self):
        html = self.client.get('/privacy/').content.decode()
        for phrase in ['one-way hash', 'Student or a Guest', 'Continue with Google', 'Gmail',
                       'no advertising or tracking cookies', 'Vercel', 'Supabase', 'verification code',
                       'Password reset', 'do not sell', 'deleted', '13 or older']:
            self.assertIn(phrase, html, phrase)
        self.assertNotIn('GDPR', html)
        self.assertNotIn('NDPR', html)

    def test_terms_cover_the_required_points(self):
        html = self.client.get('/terms/').content.decode()
        for phrase in ['13 or older', 'illegal', 'harass', 'spam', 'fake or misleading events',
                       'You are responsible for your events', 'anything you promise', 'suspend',
                       'Events happen offline', 'as is', 'Changes to these terms']:
            self.assertIn(phrase, html, phrase)

    def test_footer_links_on_signed_in_and_signed_out_pages(self):
        for path in ['/', '/accounts/login/', '/privacy/']:
            html = self.client.get(path).content.decode()
            self.assertIn('href="/privacy/"', html, path)
            self.assertIn('href="/terms/"', html, path)
        user = User.objects.create_user(username='ada', email='ada@example.com', password='x')
        self.client.force_login(user)
        html = self.client.get('/home/').content.decode()
        self.assertIn('class="epx-footer"', html)
        self.assertIn('href="/privacy/"', html)

    def test_landing_has_one_footer(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('class="epx-footer"', html)
        self.assertEqual(html.count('<footer'), 1)

    def test_agreement_line_under_google_button_and_register_button(self):
        login = self.client.get('/accounts/login/').content.decode()
        self.assertIn('By continuing you agree to our', login)
        register = self.client.get('/accounts/register/').content.decode()
        self.assertEqual(register.count('By continuing you agree to our'), 2)  # under submit + under Google
        self.assertNotIn('href="#">Terms', register)
        self.assertIn('href="/terms/" target="_blank"', register)


FEEDBACK = 'href="mailto:getinformedconcepts@gmail.com?subject=EventPulse%20feedback"'


@override_settings(**LEGAL_SETTINGS)
class FeedbackLinkTests(TestCase):

    def test_signed_out_pages_have_it_in_the_footer(self):
        for path in ['/', '/accounts/login/', '/privacy/']:
            self.assertContains(self.client.get(path), FEEDBACK, msg_prefix=path)

    def test_signed_in_menu_and_footer(self):
        self.client.force_login(User.objects.create_user(username='ada', email='ada@example.com', password='x'))
        html = self.client.get('/home/').content.decode()
        dropdown = html[html.index('id="userDropdown"'):]
        dropdown = dropdown[:dropdown.index('Sign Out')]
        self.assertIn(FEEDBACK, dropdown)                                      # account menu
        self.assertIn(FEEDBACK, html[html.index('class="epx-footer"'):])        # footer
