from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings

from .media_views import serve_media

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          include('events.urls')),
    path('accounts/', include('accounts.urls')),
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