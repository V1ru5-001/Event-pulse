# payments/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required(login_url='accounts:login')
def pricing_view(request):
    return render(request, 'payments/pricing.html')


@login_required(login_url='accounts:login')
def checkout_view(request):
    if request.method != 'POST':
        return redirect('payments:pricing')

    plan   = request.POST.get('plan', '')
    amount = request.POST.get('amount', 0)

    # Validate
    valid_plans = {'student': 1500, 'organiser': 4500}
    if plan not in valid_plans:
        messages.error(request, 'Invalid plan selected.')
        return redirect('payments:pricing')

    # TODO: integrate real payment gateway (Paystack / Flutterwave / Stripe)
    # For now simulate success and update user plan

    user = request.user
    user.plan = 'premium' if plan == 'student' else 'organiser_pro'

    # Set expiry 30 days from now
    from django.utils import timezone
    from datetime import timedelta
    user.plan_expiry = timezone.now() + timedelta(days=30)
    user.save(update_fields=['plan', 'plan_expiry'])

    plan_names = {'student': 'Student Plus', 'organiser': 'Organiser Pro'}
    messages.success(
        request,
        f'🎉 Welcome to {plan_names[plan]}! Your account has been upgraded.'
    )
    return redirect('events:home')
