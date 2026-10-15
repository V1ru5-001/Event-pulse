from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthError
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.text import slugify

from . import otp

# Session key that keeps a brand-new Google user on the "Finish your profile" page.
NEEDS_PROFILE_SESSION_KEY = 'needs_profile'

# Usernames that would collide with fixed URLs under /accounts/profile/.
RESERVED_USERNAMES = {'edit'}


def generate_username(email):
    """Unique username from the email's local part: 'ada.obi@x.com' -> 'adaobi', then 'adaobi1', 'adaobi2'…"""
    User = get_user_model()
    max_len = User._meta.get_field('username').max_length
    base = slugify((email or '').split('@')[0]).replace('-', '')[: max_len - 6] or 'user'
    candidate, n = base, 0
    while candidate in RESERVED_USERNAMES or User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f'{base}{n}'
    return candidate


def _refuse():
    """Abort the Google flow and land on our own login page with a friendly message."""
    raise ImmediateHttpResponse(redirect('accounts:login'))


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        # Returning Google users are already linked; nothing to decide.
        if sociallogin.is_existing:
            return

        addresses = sociallogin.email_addresses or []
        email = (addresses[0].email if addresses else sociallogin.user.email or '').strip()
        verified = any(a.verified and a.email.lower() == email.lower() for a in addresses)

        if not email or not verified:
            messages.error(request, "Google didn't confirm that email address, so we can't sign you in with it. "
                                    "Please use your email and password instead.")
            _refuse()

        existing = get_user_model().objects.filter(email__iexact=email).first()
        if existing:
            if not otp.is_verified(existing):
                # Someone registered this email but never confirmed it. Google has now proven
                # who owns the address, so confirm it and drop the unconfirmed password, which
                # may have been set by someone else.
                existing.set_unusable_password()
                existing.save(update_fields=['password'])
                otp.mark_verified(existing)
            # Same person, proven by Google: attach Google to the existing account.
            # Unlike allauth's built-in email authentication, this never touches a confirmed password.
            sociallogin.connect(request, existing)

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if not user.username:
            user.username = generate_username(user.email)
        user = super().save_user(request, sociallogin, form)
        request.session[NEEDS_PROFILE_SESSION_KEY] = True
        return user

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        if error == AuthError.CANCELLED:
            messages.info(request, 'Google sign-in was cancelled.')
        else:
            messages.error(request, "We couldn't sign you in with Google. Please try again or use your email and password.")
        _refuse()
