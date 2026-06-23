from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from .forms import RegisterForm

User = get_user_model()


def login_view(request):
    if request.user.is_authenticated:
        return redirect('events:home')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}! 👋')
            # always go to home after login
            return redirect('events:home')
        else:
            messages.error(request, 'Invalid credentials. Please try again.')

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('events:home')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f'Welcome to CampusPulse, {user.first_name or user.username}! 🎓 Your campus account is ready.'
            )
            # always go to home after register
            return redirect('events:home')
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    name = request.user.first_name or request.user.username
    logout(request)
    messages.info(request, f'You have been signed out. See you on campus, {name}!')
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