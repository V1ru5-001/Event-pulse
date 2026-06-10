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
    return redirect('accounts:profile', username=request.user.username)