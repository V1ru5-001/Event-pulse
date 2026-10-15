from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
from .forms import EventPulsePasswordResetForm, EventPulseSetPasswordForm
from events.views import profile_view

app_name = 'accounts'

urlpatterns = [
    path('login/',                   views.login_view,        name='login'),
    path('register/',                views.register_view,     name='register'),
    path('logout/',                  views.logout_view,       name='logout'),
    path('finish-profile/',          views.finish_profile_view, name='finish_profile'),
    path('verify-email/',            views.verify_email_view, name='verify_email'),
    path('verify-email/resend/',     views.resend_code_view,  name='resend_code'),
    path('search/',                  views.search_people,     name='search_people'),
    path('profile/edit/',            views.edit_profile_view, name='edit_profile'),
    path('profile/<str:username>/',  profile_view,            name='profile'),

    # ── Password reset (Django's built-in views, restyled templates) ──
    path('password-reset/', views.ThrottledPasswordResetView.as_view(
        form_class=EventPulsePasswordResetForm,
        template_name='accounts/password_reset.html',
        email_template_name='accounts/emails/password_reset.txt',
        subject_template_name='accounts/emails/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        form_class=EventPulseSetPasswordForm,
        template_name='accounts/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
]
