from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .adapters import NEEDS_PROFILE_SESSION_KEY


class FinishProfileMiddleware:
    """Keep brand-new Google users on "Finish your profile" until they've filled it in."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get(NEEDS_PROFILE_SESSION_KEY):
            allowed = (reverse('accounts:finish_profile'), reverse('accounts:logout'))
            path = request.path
            if not (path in allowed or path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL)):
                return redirect('accounts:finish_profile')
        return self.get_response(request)
