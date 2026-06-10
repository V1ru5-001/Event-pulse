from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('',                        views.landing_view,      name='landing'),
    path('home/',                   views.home_view,         name='home'),
    path('events/create/',          views.create_event_view, name='create'),
    path('events/<slug:slug>/',     views.event_detail_view, name='detail'),
    path('events/<slug:slug>/edit/',views.create_event_view, name='edit'),
    path('events/<slug:slug>/rsvp/', views.rsvp_view, name='rsvp'),
    path('events/<slug:slug>/rsvps/', views.manage_rsvps_view, name='manage_rsvps'),
]
