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
