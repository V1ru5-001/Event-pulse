from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

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
