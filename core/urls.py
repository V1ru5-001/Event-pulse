from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings

from accounts import views as account_views
from .media_views import serve_media

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          include('events.urls')),
    path('accounts/', include('accounts.urls')),

    # ── Google sign-in (django-allauth) ──
    # Our own login/register/logout above win; these come next so the only
    # allauth page anyone can reach is Google's callback.
    path('accounts/google/login/',    account_views.google_login, name='google_login'),
    path('accounts/3rdparty/signup/', account_views.google_signup_fallback),
    re_path(r'^accounts/(?:signup|inactive|reauthenticate|email|confirm-email|password|login/code|3rdparty|social|google/login/token)(?:/.*)?$',
            account_views.allauth_page_redirect),
    path('accounts/', include('allauth.urls')),

    path('payments/', include('payments.urls')),
    path('dashboard/',include('dashboard.urls')),
    path('social/',   include('social.urls')),
]

# Serve local media whenever you're NOT using S3/R2/B2 (USE_S3=False).
# On Vercel this only helps during local `runserver` — Vercel's disk is
# ephemeral, so set USE_S3=True there. On a host with a persistent disk
# (Render, a VPS, etc.) this keeps working in production too.
if not getattr(settings, 'USE_S3', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media),
    ]