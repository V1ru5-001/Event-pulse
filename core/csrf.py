from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.csrf import csrf_failure as default_csrf_failure


def _safe(request, url):
    return url if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) else None


def csrf_failure(request, reason=''):
    """
    A form went stale — usually a login page left open from before the user
    signed in (signing in rotates the CSRF token). The rejected POST is never
    acted on; we just send the user somewhere useful instead of a bare 403.
    """
    auth_pages = {reverse('accounts:login'), reverse('accounts:register')}
    next_url = _safe(request, request.POST.get('next') or request.GET.get('next'))

    if request.user.is_authenticated:
        if request.path in auth_pages:
            return redirect(next_url or 'events:home')
        messages.info(request, 'That page was out of date, so nothing was changed. Please try again.')
        return redirect(_safe(request, request.META.get('HTTP_REFERER')) or 'events:home')

    if request.path in auth_pages:
        messages.info(request, 'Your session expired. Please try again.')
        return redirect(request.path + ('?' + urlencode({'next': next_url}) if next_url else ''))

    return default_csrf_failure(request, reason)
