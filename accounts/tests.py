import re
from datetime import timedelta
from unittest import mock

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.providers.base import AuthError
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from . import otp, throttle, views
from .adapters import NEEDS_PROFILE_SESSION_KEY, SocialAccountAdapter, generate_username
from .models import AuthThrottle, EmailOTP

User = get_user_model()

GOOGLE_ON = {'google': {'SCOPE': ['profile', 'email'], 'APP': {'client_id': 'test-id', 'secret': 'test-secret', 'key': ''}}}
GOOGLE_OFF = {'google': {'SCOPE': ['profile', 'email']}}

# Plain HTTP, no hashed-static manifest, no whitenoise: just what the tests need.
TEST_SETTINGS = dict(
    SECURE_SSL_REDIRECT=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    SOCIALACCOUNT_PROVIDERS=GOOGLE_ON,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],  # fast hashing for tests only
)


def make_user(username='ada', email='ada@example.com', password='Str0ng!Pass99', **extra):
    return User.objects.create_user(username=username, email=email, password=password, **extra)


def google_login(email, verified=True, uid='g-123', name='Ada Obi'):
    """The SocialLogin allauth builds after Google hands back a profile."""
    account = SocialAccount(provider='google', uid=uid,
                            extra_data={'email': email, 'email_verified': verified, 'name': name})
    user = User(email=email, first_name='Ada', last_name='Obi')
    return SocialLogin(account=account, user=user,
                       email_addresses=[EmailAddress(email=email, verified=verified, primary=True)])


@override_settings(**TEST_SETTINGS)
class AdapterTestCase(TestCase):

    def request(self):
        req = RequestFactory().get('/accounts/google/login/callback/')
        req.session = SessionStore()
        req._messages = FallbackStorage(req)
        req.user = None
        return req

    def message_texts(self, req):
        return [str(m) for m in req._messages]


class UsernameGenerationTests(AdapterTestCase):

    def test_uses_slugified_local_part(self):
        self.assertEqual(generate_username('Ada.Obi+events@gmail.com'), 'adaobievents')

    def test_numeric_suffix_when_taken_case_insensitively(self):
        make_user(username='AdaObi', email='one@example.com')
        make_user(username='adaobi1', email='two@example.com')
        self.assertEqual(generate_username('ada.obi@gmail.com'), 'adaobi2')

    def test_falls_back_to_user_for_unusable_local_part(self):
        self.assertEqual(generate_username('+++@example.com'), 'user')
        make_user(username='user', email='u@example.com')
        self.assertEqual(generate_username('+++@example.com'), 'user1')

    def test_reserved_profile_path_skipped(self):
        # /accounts/profile/edit/ is the edit page, so nobody may be called "edit".
        self.assertEqual(generate_username('edit@example.com'), 'edit1')

    def test_long_local_part_fits_field(self):
        name = generate_username(('a' * 300) + '@example.com')
        self.assertLessEqual(len(name), User._meta.get_field('username').max_length)


class LinkingTests(AdapterTestCase):

    def test_verified_email_links_existing_account_and_keeps_password(self):
        existing = make_user()
        req = self.request()
        login = google_login('ADA@example.com', verified=True)
        SocialAccountAdapter(req).pre_social_login(req, login)

        self.assertEqual(login.user.pk, existing.pk)
        self.assertTrue(login.is_existing)
        self.assertTrue(SocialAccount.objects.filter(user=existing, provider='google', uid='g-123').exists())
        existing.refresh_from_db()
        self.assertTrue(existing.check_password('Str0ng!Pass99'), 'linking must not wipe the password')

    def test_unverified_email_refused_for_existing_account(self):
        existing = make_user()
        req = self.request()
        with self.assertRaises(ImmediateHttpResponse) as caught:
            SocialAccountAdapter(req).pre_social_login(req, google_login('ada@example.com', verified=False))
        self.assertEqual(caught.exception.response['Location'], '/accounts/login/')
        self.assertFalse(SocialAccount.objects.filter(user=existing).exists())
        self.assertIn("Google didn't confirm", ' '.join(self.message_texts(req)))

    def test_unverified_email_refused_for_new_account(self):
        req = self.request()
        with self.assertRaises(ImmediateHttpResponse):
            SocialAccountAdapter(req).pre_social_login(req, google_login('new@example.com', verified=False))

    def test_verified_new_email_continues_to_signup(self):
        req = self.request()
        login = google_login('new@example.com', verified=True)
        SocialAccountAdapter(req).pre_social_login(req, login)
        self.assertFalse(login.is_existing)

    def test_already_linked_account_is_left_alone(self):
        existing = make_user()
        SocialAccount.objects.create(user=existing, provider='google', uid='g-123')
        req = self.request()
        login = google_login('ada@example.com', verified=False)
        login.user = existing  # what allauth's lookup() sets for a known Google account
        SocialAccountAdapter(req).pre_social_login(req, login)  # no exception
        self.assertEqual(SocialAccount.objects.filter(user=existing).count(), 1)


class NewGoogleUserTests(AdapterTestCase):

    def test_save_user_sets_username_unusable_password_and_profile_flag(self):
        make_user(username='adaobi', email='someone@example.com')
        req = self.request()
        login = google_login('ada.obi@gmail.com')
        user = SocialAccountAdapter(req).save_user(req, login)

        user.refresh_from_db()
        self.assertEqual(user.username, 'adaobi1')
        self.assertEqual(user.email, 'ada.obi@gmail.com')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(user=user, provider='google').exists())
        self.assertTrue(req.session[NEEDS_PROFILE_SESSION_KEY])

    def test_auth_errors_return_to_login_with_message(self):
        for error, text in [(AuthError.CANCELLED, 'cancelled'), (AuthError.UNKNOWN, "couldn't sign you in")]:
            req = self.request()
            with self.assertRaises(ImmediateHttpResponse) as caught:
                SocialAccountAdapter(req).on_authentication_error(req, provider=None, error=error)
            self.assertEqual(caught.exception.response['Location'], '/accounts/login/')
            self.assertIn(text, ' '.join(self.message_texts(req)))


@override_settings(**TEST_SETTINGS)
class FinishProfileTests(TestCase):

    def sign_in_new_google_user(self):
        user = make_user(username='gina', email='gina@gmail.com', password=None)
        self.client.force_login(user)
        session = self.client.session
        session[NEEDS_PROFILE_SESSION_KEY] = True
        session.save()
        return user

    def test_new_google_user_is_kept_on_finish_page(self):
        self.sign_in_new_google_user()
        for path in ['/home/', '/calendar/', '/social/notifications/', '/accounts/profile/edit/']:
            r = self.client.get(path)
            self.assertRedirects(r, '/accounts/finish-profile/', fetch_redirect_response=False, msg_prefix=path)
        r = self.client.get('/accounts/finish-profile/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Finish your profile')
        self.assertContains(r, 'gina@gmail.com')

    def test_logout_still_reachable(self):
        self.sign_in_new_google_user()
        r = self.client.get('/accounts/logout/')
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)

    def test_finishing_saves_details_and_unlocks_app(self):
        user = self.sign_in_new_google_user()
        r = self.client.post('/accounts/finish-profile/', {
            'role': 'student', 'university': 'UNIZIK', 'department': 'Computer Science', 'year_of_study': '2'})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual((user.role, user.university, user.department, user.year_of_study),
                         ('student', 'UNIZIK', 'Computer Science', '2'))
        self.assertNotIn(NEEDS_PROFILE_SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get('/home/').status_code, 200)

    def test_guest_year_is_dropped_like_register(self):
        user = self.sign_in_new_google_user()
        self.client.post('/accounts/finish-profile/', {'role': 'guest', 'year_of_study': '3'})
        user.refresh_from_db()
        self.assertEqual((user.role, user.year_of_study), ('guest', ''))

    def test_same_validation_as_register(self):
        user = self.sign_in_new_google_user()
        r = self.client.post('/accounts/finish-profile/', {'role': 'admin', 'year_of_study': '9'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'epx-ferr')
        user.refresh_from_db()
        self.assertEqual(user.role, 'student')  # unchanged default
        self.assertTrue(self.client.session[NEEDS_PROFILE_SESSION_KEY])

    def test_existing_users_skip_finish_page(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get('/home/').status_code, 200)
        self.assertRedirects(self.client.get('/accounts/finish-profile/'), '/home/', fetch_redirect_response=False)


@override_settings(**TEST_SETTINGS)
class UrlAndButtonTests(TestCase):

    def test_our_account_urls_still_resolve_to_our_views(self):
        for path, view in [('/accounts/login/', views.login_view), ('/accounts/register/', views.register_view),
                           ('/accounts/logout/', views.logout_view), ('/accounts/profile/edit/', views.edit_profile_view),
                           ('/accounts/search/', views.search_people)]:
            self.assertEqual(resolve(path).func, view, path)

    def test_allauth_pages_redirect_to_ours(self):
        for path in ['/accounts/signup/', '/accounts/inactive/', '/accounts/email/', '/accounts/password/reset/',
                     '/accounts/password/change/', '/accounts/confirm-email/', '/accounts/reauthenticate/',
                     '/accounts/3rdparty/', '/accounts/3rdparty/login/error/', '/accounts/3rdparty/login/cancelled/',
                     '/accounts/social/connections/', '/accounts/login/code/confirm/', '/accounts/google/login/token/']:
            r = self.client.get(path)
            self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False, msg_prefix=path)

    def test_social_signup_fallback_goes_to_register(self):
        r = self.client.get('/accounts/3rdparty/signup/')
        self.assertRedirects(r, '/accounts/register/', fetch_redirect_response=False)

    def test_google_login_get_goes_to_our_login_page(self):
        r = self.client.get('/accounts/google/login/')
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)

    def test_google_login_post_sends_user_to_google(self):
        r = self.client.post('/accounts/google/login/', {'process': 'login'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('https://accounts.google.com/'), r['Location'])
        self.assertIn('client_id=test-id', r['Location'])
        self.assertRegex(r['Location'], r'scope=(email\+profile|profile\+email)&')
        self.assertIn('redirect_uri=https%3A%2F%2Ftestserver%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F', r['Location'])

    def test_google_login_requires_csrf(self):
        from django.test import Client
        r = Client(enforce_csrf_checks=True).post('/accounts/google/login/', {'process': 'login'})
        self.assertEqual(r.status_code, 403)

    def test_buttons_on_login_and_register(self):
        for path in ['/accounts/login/', '/accounts/register/']:
            r = self.client.get(path)
            self.assertContains(r, 'Continue with Google', msg_prefix=path)
            self.assertContains(r, 'action="/accounts/google/login/"', msg_prefix=path)
            self.assertContains(r, 'class="epx-or"', msg_prefix=path)

    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_OFF)
    def test_buttons_hidden_and_flow_off_without_credentials(self):
        for path in ['/accounts/login/', '/accounts/register/']:
            self.assertNotContains(self.client.get(path), 'Continue with Google', msg_prefix=path)
        r = self.client.post('/accounts/google/login/', {'process': 'login'})
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)

    def test_login_button_carries_next(self):
        r = self.client.get('/accounts/login/?next=/calendar/')
        self.assertContains(r, '<input type="hidden" name="next" value="/calendar/" />', count=2)

    def test_register_and_password_login_still_work_with_two_backends(self):
        r = self.client.post('/accounts/register/', {
            'first_name': 'Ben', 'username': 'ben', 'email': 'ben@example.com', 'role': 'guest',
            'password1': 'Str0ng!Pass99', 'password2': 'Str0ng!Pass99', 'terms': 'on'})
        self.assertRedirects(r, '/accounts/verify-email/', fetch_redirect_response=False)
        code = re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
        r = self.client.post('/accounts/verify-email/', {'code': code})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post('/accounts/login/', {'username': 'ben@example.com', 'password': 'Str0ng!Pass99'})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/home/').status_code, 200)


# ═══════════════════════ Part D: email codes + password reset ═══════════════════════

def last_code():
    return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)


def a_wrong_code(right):
    return '000000' if right != '000000' else '111111'


REGISTER = {'first_name': 'Cara', 'username': 'cara', 'email': 'cara@example.com', 'role': 'student',
            'password1': 'Str0ng!Pass99', 'password2': 'Str0ng!Pass99', 'terms': 'on'}


@override_settings(**TEST_SETTINGS)
class OtpServiceTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_only_a_hash_is_stored(self):
        otp.send_code(self.user)
        code = last_code()
        row = EmailOTP.objects.get(user=self.user)
        self.assertNotIn(code, row.code_hash)
        self.assertEqual(len(row.code_hash), 64)
        self.assertFalse(otp.is_verified(self.user))

    def test_correct_code_verifies_and_removes_row(self):
        otp.send_code(self.user)
        self.assertEqual(otp.verify_code(self.user, last_code()), (otp.OK, 0))
        self.assertTrue(otp.is_verified(self.user))

    def test_code_expires_after_ten_minutes(self):
        otp.send_code(self.user)
        code = last_code()
        later = timezone.now() + timedelta(minutes=10, seconds=1)
        with mock.patch('accounts.otp.timezone.now', return_value=later):
            self.assertEqual(otp.verify_code(self.user, code)[0], otp.EXPIRED)
        self.assertFalse(otp.is_verified(self.user))

    def test_five_wrong_tries_invalidate_the_code(self):
        otp.send_code(self.user)
        code = last_code()
        results = [otp.verify_code(self.user, a_wrong_code(code)) for _ in range(5)]
        self.assertEqual(results[:4], [(otp.WRONG, 4), (otp.WRONG, 3), (otp.WRONG, 2), (otp.WRONG, 1)])
        self.assertEqual(results[4][0], otp.LOCKED)
        # Even the right code is refused now; a new one is needed.
        self.assertEqual(otp.verify_code(self.user, code)[0], otp.LOCKED)

    def test_locked_code_can_be_replaced_without_waiting(self):
        otp.send_code(self.user)
        for _ in range(5):
            otp.verify_code(self.user, 'abcdef')
        sent, _ = otp.send_code(self.user)
        self.assertTrue(sent)
        self.assertEqual(otp.verify_code(self.user, last_code())[0], otp.OK)

    def test_resend_cooldown_is_sixty_seconds(self):
        otp.send_code(self.user)
        sent, wait = otp.send_code(self.user)
        self.assertFalse(sent)
        self.assertTrue(55 <= wait <= 60, wait)
        self.assertEqual(len(mail.outbox), 1)
        later = timezone.now() + timedelta(seconds=61)
        with mock.patch('accounts.otp.timezone.now', return_value=later):
            self.assertTrue(otp.send_code(self.user)[0])
        self.assertEqual(len(mail.outbox), 2)

    def test_new_code_replaces_old_and_resets_attempts(self):
        otp.send_code(self.user)
        old = last_code()
        otp.verify_code(self.user, 'abcdef')
        later = timezone.now() + timedelta(seconds=61)
        with mock.patch('accounts.otp.timezone.now', return_value=later):
            otp.send_code(self.user)
        self.assertEqual(EmailOTP.objects.get(user=self.user).attempts, 0)
        if old != last_code():
            self.assertEqual(otp.verify_code(self.user, old)[0], otp.WRONG)
        self.assertEqual(otp.verify_code(self.user, last_code())[0], otp.OK)

    def test_uses_constant_time_comparison(self):
        otp.send_code(self.user)
        with mock.patch('accounts.otp.constant_time_compare', return_value=False) as cmp:
            otp.verify_code(self.user, last_code())
        cmp.assert_called_once()

    def test_failed_send_allows_immediate_retry(self):
        with mock.patch('accounts.otp.send_mail', side_effect=OSError('smtp down')), \
                self.assertLogs('accounts.otp', level='ERROR') as logs:
            self.assertEqual(otp.send_code(self.user), (False, 0))
        self.assertNotRegex(' '.join(logs.output), r'\b\d{6}\b')  # the code is never logged
        self.assertTrue(otp.send_code(self.user)[0])

    def test_existing_users_without_row_are_verified(self):
        self.assertTrue(otp.is_verified(self.user))


@override_settings(**TEST_SETTINGS)
class RegisterAndVerifyFlowTests(TestCase):

    def test_register_sends_code_and_does_not_sign_in(self):
        r = self.client.post('/accounts/register/', REGISTER)
        self.assertRedirects(r, '/accounts/verify-email/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['cara@example.com'])
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.client.get('/home/'), '/accounts/login/?next=/home/', fetch_redirect_response=False)

        page = self.client.get('/accounts/verify-email/')
        self.assertContains(page, 'Check your email')
        self.assertContains(page, 'ca••@example.com')
        self.assertNotContains(page, last_code())

    def test_right_code_signs_in(self):
        self.client.post('/accounts/register/', REGISTER)
        r = self.client.post('/accounts/verify-email/', {'code': last_code()})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/home/').status_code, 200)
        self.assertTrue(otp.is_verified(User.objects.get(email='cara@example.com')))

    def test_wrong_code_five_times_then_resend(self):
        self.client.post('/accounts/register/', REGISTER)
        code = last_code()
        for left in (4, 3, 2, 1):
            r = self.client.post('/accounts/verify-email/', {'code': a_wrong_code(code)})
            self.assertContains(r, f"{left} {'try' if left == 1 else 'tries'} left")
        r = self.client.post('/accounts/verify-email/', {'code': a_wrong_code(code)})
        self.assertContains(r, 'Too many wrong tries')
        r = self.client.post('/accounts/verify-email/', {'code': code})
        self.assertContains(r, 'Too many wrong tries')
        self.client.post('/accounts/verify-email/resend/')
        self.assertEqual(len(mail.outbox), 2)
        r = self.client.post('/accounts/verify-email/', {'code': last_code()})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)

    def test_resend_respects_cooldown(self):
        self.client.post('/accounts/register/', REGISTER)
        r = self.client.post('/accounts/verify-email/resend/', follow=True)
        self.assertContains(r, 'Please wait')
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(r, 'disabled')

    def test_verify_page_needs_a_pending_signup(self):
        self.assertRedirects(self.client.get('/accounts/verify-email/'), '/accounts/login/', fetch_redirect_response=False)
        self.assertRedirects(self.client.post('/accounts/verify-email/resend/'), '/accounts/login/', fetch_redirect_response=False)

    def test_other_browser_cannot_enter_the_code(self):
        self.client.post('/accounts/register/', REGISTER)
        other = self.client_class()
        r = other.post('/accounts/verify-email/', {'code': last_code()})
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)
        self.assertFalse(otp.is_verified(User.objects.get(email='cara@example.com')))

    def test_unverified_login_sends_new_code_instead_of_signing_in(self):
        self.client.post('/accounts/register/', REGISTER)
        browser = self.client_class()
        later = timezone.now() + timedelta(seconds=61)
        with mock.patch('accounts.otp.timezone.now', return_value=later):
            r = browser.post('/accounts/login/', {'username': 'cara@example.com', 'password': 'Str0ng!Pass99'})
        self.assertRedirects(r, '/accounts/verify-email/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', browser.session)
        self.assertEqual(len(mail.outbox), 2)
        with mock.patch('accounts.otp.timezone.now', return_value=later):
            r = browser.post('/accounts/verify-email/', {'code': last_code()})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)

    def test_unverified_login_within_cooldown_sends_nothing_new(self):
        self.client.post('/accounts/register/', REGISTER)
        r = self.client.post('/accounts/login/', {'username': 'cara@example.com', 'password': 'Str0ng!Pass99'}, follow=True)
        self.assertContains(r, 'We already sent you a code')
        self.assertEqual(len(mail.outbox), 1)

    def test_unverified_wrong_password_shows_normal_error(self):
        self.client.post('/accounts/register/', REGISTER)
        r = self.client.post('/accounts/login/', {'username': 'cara@example.com', 'password': 'nope'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_existing_verified_users_log_in_as_before(self):
        make_user()
        r = self.client.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'Str0ng!Pass99'})
        self.assertRedirects(r, '/home/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class GoogleAndVerificationTests(AdapterTestCase):

    def test_google_users_skip_the_code(self):
        req = self.request()
        user = SocialAccountAdapter(req).save_user(req, google_login('gina@gmail.com'))
        self.assertTrue(otp.is_verified(user))
        self.assertEqual(len(mail.outbox), 0)

    def test_google_link_to_unconfirmed_account_confirms_it_and_drops_password(self):
        squatter = make_user(email='victim@gmail.com', username='squatter')
        otp.send_code(squatter)
        req = self.request()
        SocialAccountAdapter(req).pre_social_login(req, google_login('victim@gmail.com', verified=True))
        squatter.refresh_from_db()
        self.assertTrue(otp.is_verified(squatter))
        self.assertFalse(squatter.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(user=squatter).exists())


@override_settings(**TEST_SETTINGS)
class PasswordResetTests(TestCase):
    HOST = 'event-pulse-dun.vercel.app'

    def request_reset(self, email):
        return self.client.post('/accounts/password-reset/', {'email': email}, HTTP_HOST=self.HOST, secure=True)

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get('/accounts/login/'), 'href="/accounts/password-reset/"')
        self.assertContains(self.client.get('/accounts/password-reset/'), 'Forgot your password?')

    def test_same_response_for_known_and_unknown_emails(self):
        make_user()
        known = self.request_reset('ada@example.com')
        unknown = self.request_reset('nobody@example.com')
        self.assertRedirects(known, '/accounts/password-reset/sent/', fetch_redirect_response=False)
        self.assertRedirects(unknown, '/accounts/password-reset/sent/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        page = self.client.get('/accounts/password-reset/sent/')
        self.assertContains(page, 'If that email belongs to an EventPulse account')

    def test_full_reset_flow_uses_the_real_site_address(self):
        user = make_user()
        self.request_reset('ADA@example.com')
        body = mail.outbox[0].body
        self.assertIn('Reset your EventPulse password', mail.outbox[0].subject)
        self.assertNotIn('example.com/', body)  # not the sites-framework placeholder
        link = re.search(r'https://event-pulse-dun\.vercel\.app(/accounts/password-reset/\S+/)', body).group(1)
        r = self.client.get(link, HTTP_HOST=self.HOST, secure=True)
        self.assertEqual(r.status_code, 302)  # Django moves the token into the session
        set_url = r['Location']
        self.assertContains(self.client.get(set_url, HTTP_HOST=self.HOST, secure=True), 'Choose a new password')
        r = self.client.post(set_url, {'new_password1': 'N3w!Passw0rd77', 'new_password2': 'N3w!Passw0rd77'},
                             HTTP_HOST=self.HOST, secure=True)
        self.assertRedirects(r, '/accounts/password-reset/complete/', fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.check_password('N3w!Passw0rd77'))
        self.assertContains(self.client.get(r['Location'], HTTP_HOST=self.HOST, secure=True), 'Password changed')

    def test_bad_link_shows_expired_page(self):
        self.assertContains(self.client.get('/accounts/password-reset/MQ/set-password/'), 'This link has expired')

    def test_google_only_account_gets_google_email_and_same_page(self):
        gina = make_user(username='gina', email='gina@gmail.com', password=None)
        SocialAccount.objects.create(user=gina, provider='google', uid='g-1')
        r = self.request_reset('gina@gmail.com')
        self.assertRedirects(r, '/accounts/password-reset/sent/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('You signed up with Google', mail.outbox[0].body)
        self.assertIn('https://event-pulse-dun.vercel.app/accounts/login/', mail.outbox[0].body)
        self.assertNotIn('password-reset/', mail.outbox[0].body)

    def test_reset_confirms_an_unverified_email(self):
        user = make_user()
        otp.send_code(user)
        self.request_reset('ada@example.com')
        link = re.search(r'https://[^/\s]+(/accounts/password-reset/\S+/)', mail.outbox[-1].body).group(1)
        set_url = self.client.get(link, HTTP_HOST=self.HOST, secure=True)['Location']
        self.client.post(set_url, {'new_password1': 'N3w!Passw0rd77', 'new_password2': 'N3w!Passw0rd77'}, HTTP_HOST=self.HOST, secure=True)
        self.assertTrue(otp.is_verified(user))


# ═══════════════════════ Part E: rate limiting ═══════════════════════



def login_as(client, email, password, ip='10.0.0.1'):
    return client.post('/accounts/login/', {'username': email, 'password': password}, REMOTE_ADDR=ip)


@override_settings(**TEST_SETTINGS, TRUST_X_FORWARDED_FOR=False)
class ClientIpTests(TestCase):

    def req(self, remote='127.0.0.1', forwarded=None):
        meta = {'REMOTE_ADDR': remote}
        if forwarded is not None:
            meta['HTTP_X_FORWARDED_FOR'] = forwarded
        return RequestFactory().get('/', **meta)

    def test_header_ignored_off_vercel(self):
        self.assertEqual(throttle.client_ip(self.req('203.0.113.9', '1.2.3.4')), '203.0.113.9')

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_vercel_header_used_on_vercel(self):
        self.assertEqual(throttle.client_ip(self.req('127.0.0.1', '198.51.100.7')), '198.51.100.7')
        self.assertEqual(throttle.client_ip(self.req('127.0.0.1', '198.51.100.7, 10.0.0.1')), '198.51.100.7')
        self.assertEqual(throttle.client_ip(self.req('127.0.0.1', '2001:db8::1')), '2001:db8::1')

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_garbage_header_falls_back(self):
        self.assertEqual(throttle.client_ip(self.req('127.0.0.1', 'not-an-ip')), '127.0.0.1')


@override_settings(**TEST_SETTINGS, TRUST_X_FORWARDED_FOR=False)
class LoginLockoutTests(TestCase):

    def setUp(self):
        make_user()

    def test_five_failures_lock_the_account_for_that_ip(self):
        for _ in range(4):
            r = login_as(self.client, 'ada@example.com', 'wrong')
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Invalid credentials')
        r = login_as(self.client, 'ada@example.com', 'wrong')
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "Let's take a breather", status_code=429)
        self.assertContains(r, '15 minutes', status_code=429)
        self.assertContains(r, 'class="epx-authcard"', status_code=429)
        # 6th attempt, even with the right password, is refused.
        r = login_as(self.client, 'ada@example.com', 'Str0ng!Pass99')
        self.assertEqual(r.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_lockout_is_per_account_and_ip(self):
        for _ in range(5):
            login_as(self.client, 'ada@example.com', 'wrong', ip='10.0.0.1')
        self.assertEqual(login_as(self.client_class(), 'ada@example.com', 'Str0ng!Pass99', ip='10.0.0.2').status_code, 302)
        make_user(username='ben', email='ben@example.com')
        self.assertEqual(login_as(self.client_class(), 'ben@example.com', 'Str0ng!Pass99', ip='10.0.0.1').status_code, 302)

    def test_email_case_does_not_dodge_the_counter(self):
        for email in ['ada@example.com', 'ADA@example.com', ' Ada@Example.com', 'ada@EXAMPLE.com']:
            login_as(self.client, email, 'wrong')
        self.assertEqual(login_as(self.client, 'aDa@example.com', 'wrong').status_code, 429)

    def test_lock_lifts_after_fifteen_minutes(self):
        for _ in range(5):
            login_as(self.client, 'ada@example.com', 'wrong')
        later = timezone.now() + timedelta(minutes=15, seconds=1)
        with mock.patch('accounts.throttle.timezone.now', return_value=later):
            r = login_as(self.client, 'ada@example.com', 'Str0ng!Pass99')
        self.assertEqual(r.status_code, 302)

    def test_successful_login_resets_the_count(self):
        for _ in range(4):
            login_as(self.client, 'ada@example.com', 'wrong')
        login_as(self.client, 'ada@example.com', 'Str0ng!Pass99')
        self.client.logout()
        for _ in range(4):
            self.assertEqual(login_as(self.client, 'ada@example.com', 'wrong').status_code, 200)

    def test_one_ip_trying_many_accounts_is_stopped(self):
        for i in range(29):
            self.assertEqual(login_as(self.client, f'user{i}@example.com', 'wrong').status_code, 200)
        self.assertEqual(login_as(self.client, 'user29@example.com', 'wrong').status_code, 429)
        self.assertEqual(login_as(self.client_class(), 'ada@example.com', 'Str0ng!Pass99').status_code, 429)
        self.assertEqual(login_as(self.client_class(), 'ada@example.com', 'Str0ng!Pass99', ip='10.0.0.9').status_code, 302)

    def test_nothing_personal_is_stored(self):
        login_as(self.client, 'ada@example.com', 'wrong', ip='198.51.100.23')
        keys = ' '.join(AuthThrottle.objects.values_list('key', flat=True))
        self.assertNotIn('ada', keys)
        self.assertNotIn('198.51', keys)

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_spoofed_header_counts_by_real_vercel_ip(self):
        # On Vercel the header holds the real IP; whatever a client sends is overwritten upstream.
        for _ in range(5):
            self.client.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'wrong'},
                             REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='198.51.100.1')
        r = self.client.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'Str0ng!Pass99'},
                             REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='198.51.100.2')
        self.assertEqual(r.status_code, 302)  # a different visitor is not caught by someone else's lock

    def test_works_with_csrf_failure_view(self):
        for _ in range(5):
            login_as(self.client, 'ada@example.com', 'wrong')
        strict = self.client_class(enforce_csrf_checks=True)
        strict.get('/accounts/login/')
        # A stale form is turned back by core/csrf.py (fresh login page), not a bare 403, and isn't counted.
        r = strict.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'x', 'csrfmiddlewaretoken': 'stale' * 13},
                        REMOTE_ADDR='10.0.0.1')
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)
        # With a valid token the lockout page is shown.
        token = strict.cookies['csrftoken'].value
        r = strict.post('/accounts/login/', {'username': 'ada@example.com', 'password': 'Str0ng!Pass99',
                                             'csrfmiddlewaretoken': token}, REMOTE_ADDR='10.0.0.1')
        self.assertEqual(r.status_code, 429)


@override_settings(**TEST_SETTINGS, TRUST_X_FORWARDED_FOR=False)
class OtherThrottleTests(TestCase):

    def test_register_limited_per_ip(self):
        for i in range(10):
            r = self.client.post('/accounts/register/', {'username': f'x{i}', 'email': 'bad'})
            self.assertEqual(r.status_code, 200)
        r = self.client.post('/accounts/register/', {'username': 'x', 'email': 'bad'})
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, '1 hour', status_code=429)

    def pending(self):
        self.client.post('/accounts/register/', REGISTER)
        return User.objects.get(email='cara@example.com')

    def test_code_checks_limited_per_user(self):
        self.pending()
        for _ in range(15):
            self.assertEqual(self.client.post('/accounts/verify-email/', {'code': 'abcdef'}).status_code, 200)
        self.assertEqual(self.client.post('/accounts/verify-email/', {'code': 'abcdef'}).status_code, 429)

    def test_resends_limited_per_user(self):
        user = self.pending()
        for i in range(5):
            later = timezone.now() + timedelta(seconds=61 * (i + 1))
            with mock.patch('accounts.otp.timezone.now', return_value=later):
                self.assertEqual(self.client.post('/accounts/verify-email/resend/').status_code, 302)
        self.assertEqual(self.client.post('/accounts/verify-email/resend/').status_code, 429)
        self.assertEqual(len(mail.outbox), 6)  # register + 5 resends
        self.assertFalse(otp.is_verified(user))

    def test_reset_limited_per_email_and_ip(self):
        make_user()
        for _ in range(3):
            self.assertEqual(self.client.post('/accounts/password-reset/', {'email': 'ada@example.com'}).status_code, 302)
        r = self.client.post('/accounts/password-reset/', {'email': 'ADA@example.com'})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(mail.outbox), 3)
        # Unknown emails are limited the same way, so the limit reveals nothing.
        for _ in range(3):
            self.client.post('/accounts/password-reset/', {'email': 'ghost@example.com'}, REMOTE_ADDR='10.9.9.9')
        self.assertEqual(self.client.post('/accounts/password-reset/', {'email': 'ghost@example.com'}, REMOTE_ADDR='10.9.9.9').status_code, 429)

    def test_reset_limited_per_ip(self):
        for i in range(5):
            self.client.post('/accounts/password-reset/', {'email': f'p{i}@example.com'})
        self.assertEqual(self.client.post('/accounts/password-reset/', {'email': 'p9@example.com'}).status_code, 429)
