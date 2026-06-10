from django.urls import path
from . import views
from events.views import profile_view

app_name = 'accounts'

urlpatterns = [
    path('login/',                   views.login_view,        name='login'),
    path('register/',                views.register_view,     name='register'),
    path('logout/',                  views.logout_view,       name='logout'),
    path('profile/edit/',            views.edit_profile_view, name='edit_profile'),
    path('profile/<str:username>/',  profile_view,            name='profile'),
]