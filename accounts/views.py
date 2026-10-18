from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings

from django.contrib.auth.views import PasswordResetView

from . import otp, throttle
from .adapters import NEEDS_PROFILE_SESSION_KEY
from .forms import RegisterForm, FinishProfileForm

User = get_user_model()


def _next_url(request):
    """The page the user was heading to (?next=), if it's on this site."""
    url = request.POST.get('next') or request.GET.get('next')
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return None


def login_view(request):
    # Already signed in (e.g. an old tab): skip the form and carry on.
    if request.user.is_authenticated:
        return redirect(_next_url(request) or 'events:home')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST':
        ip = throttle.client_ip(request)
        account = f"{request.POST.get('username', '')}|{ip}"
        wait = throttle.seconds_locked(('login', account), ('login_ip', ip))
        if wait:
            return throttle.locked_response(request, wait)

        if form.is_valid():
            throttle.clear('login', account)
            user = form.get_user()
            if not otp.is_verified(user):
                # Right password, but the email was never confirmed: send a code instead of letting them in.
                return _start_email_check(request, user, _next_url(request))
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}! 👋')
            return redirect(_next_url(request) or 'events:home')
        else:
            locked = throttle.hit('login', account)
            locked = throttle.hit('login_ip', ip) or locked
            if locked:
                return throttle.locked_response(request, throttle.seconds_locked(('login', account), ('login_ip', ip)))
            messages.error(request, 'Invalid credentials. Please try again.')

    return render(request, 'accounts/login.html', {
        'form': form, 'next': _next_url(request) or '', 'google_enabled': _google_enabled(),
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect(_next_url(request) or 'events:home')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST':
        ip = throttle.client_ip(request)
        wait = throttle.seconds_locked(('register_ip', ip))
        if wait:
            return throttle.locked_response(request, wait)
        throttle.hit('register_ip', ip)

        if form.is_valid():
            user = form.save()
            # The account stays unverified until the emailed code is entered.
            return _start_email_check(request, user, None)
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'accounts/register.html', {
        'form': form, 'next': _next_url(request) or '', 'google_enabled': _google_enabled(),
    })


# ── Email verification code ──────────────────────────────
# The account waiting for a code is remembered in the session, so only the
# browser that just registered (or knew the password) can enter it.

OTP_USER_SESSION_KEY = 'otp_user_id'
OTP_NEXT_SESSION_KEY = 'otp_next'
OTP_SEND_FAILED_KEY  = 'otp_send_failed'

EMAIL_SEND_ERROR = "We couldn't send email right now. Please try again in a few minutes."


def _record_send(request, sent, wait):
    """Remember whether the last code email failed, so the verify page can say so."""
    if sent:
        request.session.pop(OTP_SEND_FAILED_KEY, None)
    elif not wait:
        request.session[OTP_SEND_FAILED_KEY] = True


def _start_email_check(request, user, next_url):
    request.session[OTP_USER_SESSION_KEY] = user.pk
    request.session[OTP_NEXT_SESSION_KEY] = next_url or ''
    sent, wait = otp.send_code(user)
    _record_send(request, sent, wait)
    if sent:
        messages.info(request, f'We sent a 6-digit code to {user.email}.')
    elif wait:
        messages.info(request, 'We already sent you a code. Check your inbox, or ask for a new one in a moment.')
    return redirect('accounts:verify_email')


def _pending_user(request):
    pk = request.session.get(OTP_USER_SESSION_KEY)
    return User.objects.filter(pk=pk).first() if pk else None


def _mask_email(email):
    name, _, domain = email.partition('@')
    return f'{name[:2]}{"•" * max(1, len(name) - 2)}@{domain}'


def verify_email_view(request):
    user = _pending_user(request)
    if user is None:
        return redirect('accounts:login')
    if otp.is_verified(user):
        request.session.pop(OTP_USER_SESSION_KEY, None)
        return redirect('accounts:login')

    error = ''
    if request.method == 'POST':
        ip = throttle.client_ip(request)
        wait = throttle.seconds_locked(('otp_verify_ip', ip), ('otp_verify_user', user.pk))
        if wait:
            return throttle.locked_response(request, wait)
        throttle.hit('otp_verify_ip', ip)
        throttle.hit('otp_verify_user', user.pk)

        result, left = otp.verify_code(user, request.POST.get('code'))
        if result == otp.OK:
            next_url = request.session.get(OTP_NEXT_SESSION_KEY) or 'events:home'
            for key in (OTP_USER_SESSION_KEY, OTP_NEXT_SESSION_KEY, OTP_SEND_FAILED_KEY):
                request.session.pop(key, None)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Email confirmed. Welcome to EventPulse, {user.first_name or user.username}! 🎉')
            return redirect(next_url)
        error = {
            otp.WRONG:   f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left.",
            otp.EXPIRED: 'That code has expired. Send yourself a new one.',
            otp.LOCKED:  'Too many wrong tries. Send yourself a new code.',
        }.get(result, 'Something went wrong. Send yourself a new code.')

    return render(request, 'accounts/verify_email.html', {
        'masked_email': _mask_email(user.email),
        'error': error,
        'resend_wait': otp.seconds_until_resend(user),
        'send_failed': request.session.get(OTP_SEND_FAILED_KEY, False),
    })


def resend_code_view(request):
    user = _pending_user(request)
    if request.method != 'POST' or user is None:
        return redirect('accounts:verify_email' if user else 'accounts:login')

    ip = throttle.client_ip(request)
    locked_for = throttle.seconds_locked(('otp_resend_ip', ip), ('otp_resend_user', user.pk))
    if locked_for:
        return throttle.locked_response(request, locked_for)

    sent, wait = otp.send_code(user)
    _record_send(request, sent, wait)
    if sent:
        # Only codes that actually went out count towards the resend limit.
        throttle.hit('otp_resend_ip', ip)
        throttle.hit('otp_resend_user', user.pk)
        messages.info(request, 'New code sent. Check your inbox.')
    elif wait:
        messages.info(request, f'Please wait {wait} seconds before asking for another code.')
    return redirect('accounts:verify_email')


class ThrottledPasswordResetView(PasswordResetView):
    """
    Django's reset-request view, limited per IP and per email address.

    Every request counts towards the limits (including unknown addresses, so
    the limit itself doesn't reveal which addresses have accounts), except
    one whose email failed to send: that isn't the person's fault, and
    counting it would lock them out while email is broken.
    """

    send_failed = False

    def post(self, request, *args, **kwargs):
        ip, email = throttle.client_ip(request), request.POST.get('email', '')
        wait = throttle.seconds_locked(('reset_ip', ip), ('reset_email', email))
        if wait:
            return throttle.locked_response(request, wait)
        response = super().post(request, *args, **kwargs)
        if not self.send_failed:
            throttle.hit('reset_ip', ip)
            throttle.hit('reset_email', email)
        return response

    def form_valid(self, form):
        response = super().form_valid(form)  # sends the email(s)
        if form.send_failed:
            self.send_failed = True
            return self.render_to_response(self.get_context_data(form=form, send_error=EMAIL_SEND_ERROR))
        return response


# ── Google sign-in (django-allauth) ──────────────────────

def _google_enabled():
    return bool(settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP'))


def google_login(request):
    """Start Google sign-in. Only the POST from our buttons is accepted; a plain visit goes to our login page."""
    if request.method != 'POST' or not _google_enabled():
        return redirect('accounts:login')
    from allauth.socialaccount.providers.google.views import oauth2_login
    return oauth2_login(request)


def allauth_page_redirect(request, *args, **kwargs):
    """allauth's own login/signup/account pages aren't used; send people to ours."""
    if request.user.is_authenticated:
        return redirect('events:home')
    return redirect('accounts:login')


def google_signup_fallback(request):
    """allauth's social sign-up form only appears when it can't sign someone up automatically."""
    messages.error(request, "We couldn't create an account from your Google sign-in. Please register with your email instead.")
    return redirect('accounts:register')


@login_required(login_url='accounts:login')
def finish_profile_view(request):
    if not request.session.get(NEEDS_PROFILE_SESSION_KEY):
        return redirect('events:home')

    form = FinishProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            request.session.pop(NEEDS_PROFILE_SESSION_KEY, None)
            messages.success(request, f'Welcome to EventPulse, {user.first_name or user.username}! 🎉')
            return redirect('events:home')
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'accounts/finish_profile.html', {'form': form})


def logout_view(request):
    name = request.user.first_name or request.user.username
    logout(request)
    messages.info(request, f'You have been signed out. See you soon, {name}!')
    return redirect('accounts:login')

@login_required
def edit_profile_view(request):
    u = request.user
    if request.method == 'POST':
        u.first_name    = request.POST.get('first_name', '').strip()
        u.last_name     = request.POST.get('last_name', '').strip()
        u.username      = request.POST.get('username', u.username).strip()
        u.university    = request.POST.get('university', '').strip()
        u.department    = request.POST.get('department', '').strip()
        u.year_of_study = request.POST.get('year_of_study', '')
        u.bio           = request.POST.get('bio', '').strip()
        u.phone_number  = request.POST.get('phone_number', '').strip()

        # Guard against privilege escalation — never let a form set 'admin'
        submitted_role = request.POST.get('role', u.role)
        if submitted_role in {'student', 'society', 'staff'}:
            u.role = submitted_role

        if 'profile_picture' in request.FILES:
            u.profile_picture = request.FILES['profile_picture']

        u.save()
        messages.success(request, 'Profile updated.')
        return redirect('accounts:profile', username=u.username)

    return render(request, 'accounts/edit_profile.html', {
        'year_choices': User.YearOfStudy.choices,
        'role_choices': [c for c in User.Role.choices if c[0] != 'admin'],
    })

@login_required(login_url='accounts:login')
def search_people(request):
    """People search — find users by name or username."""
    User = get_user_model()
    query = request.GET.get('q', '').strip()

    people = User.objects.none()
    if query:
        people = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(pk=request.user.pk).order_by('username')[:50]

    # Which of these the current user already follows (for button state)
    following_ids = set(
        request.user.following_set.values_list('following_id', flat=True)
    )

    return render(request, 'accounts/search_people.html', {
        'query':         query,
        'people':        people,
        'following_ids': following_ids,
    })