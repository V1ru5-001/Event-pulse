from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.urls import reverse

from . import otp

User = get_user_model()


class RegisterForm(UserCreationForm):
    """
    Extended registration form that collects all university fields.
    """

    first_name    = forms.CharField(max_length=100, required=False, label='Full Name')
    email         = forms.EmailField(required=True,  label='Email')
    role          = forms.ChoiceField(
        choices=[('student', 'Student'), ('guest', 'Guest')],
        initial='student',
        required=True,
        label='I am registering as',
    )
    university    = forms.CharField(max_length=200,  required=False, label='University')
    department    = forms.CharField(max_length=200,  required=False, label='Faculty / Department')
    year_of_study = forms.ChoiceField(
        choices=[('', 'Select your year')] + list(User.YearOfStudy.choices),
        required=False,
        label='Year of Study',
    )

    class Meta:
        model  = User
        fields = [
            'username', 'first_name', 'email',
            'password1', 'password2',
            'role', 'university', 'department', 'year_of_study',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email         = self.cleaned_data['email']
        user.first_name    = self.cleaned_data.get('first_name', '')
        user.role          = self.cleaned_data.get('role', 'student')
        user.university    = self.cleaned_data.get('university', '')
        user.department    = self.cleaned_data.get('department', '')
        user.year_of_study = self.cleaned_data.get('year_of_study', '') if user.role == 'student' else ''
        if commit:
            user.save()
        return user


class FinishProfileForm(forms.ModelForm):
    """
    The register-page details for people who signed up with Google.
    Reuses RegisterForm's field definitions so the validation is identical.
    """

    role          = RegisterForm.base_fields['role']
    university    = RegisterForm.base_fields['university']
    department    = RegisterForm.base_fields['department']
    year_of_study = RegisterForm.base_fields['year_of_study']

    class Meta:
        model  = User
        fields = ['role', 'university', 'department', 'year_of_study']

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role != 'student':
            user.year_of_study = ''
        if commit:
            user.save()
        return user


class EventPulsePasswordResetForm(PasswordResetForm):
    """
    Django's reset form, plus a "you signed up with Google" email for accounts
    that have no password. The page shows the same message either way.
    """

    def save(self, **kwargs):
        request = kwargs.get('request')
        # Build links from the address the person is actually using, not the sites-framework placeholder.
        if request is not None and not kwargs.get('domain_override'):
            kwargs['domain_override'] = request.get_host()
        super().save(**kwargs)

        domain = kwargs.get('domain_override')
        protocol = 'https' if kwargs.get('use_https') else 'http'
        email = self.cleaned_data['email']
        google_only = User._default_manager.filter(
            email__iexact=email, is_active=True, socialaccount__provider='google',
        ).distinct()
        for user in google_only:
            if user.has_usable_password():
                continue
            self.send_mail(
                'accounts/emails/password_reset_google_subject.txt',
                'accounts/emails/password_reset_google.txt',
                {'user': user, 'login_url': f"{protocol}://{domain}{reverse('accounts:login')}"},
                kwargs.get('from_email'),
                user.email,
            )


class EventPulseSetPasswordForm(SetPasswordForm):
    """Opening the emailed reset link proves the person owns the address, so it also confirms the email."""

    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            otp.mark_verified(user)
        return user
