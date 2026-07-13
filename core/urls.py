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

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media),
    ]