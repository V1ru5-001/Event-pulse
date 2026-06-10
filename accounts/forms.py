from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterForm(UserCreationForm):
    """
    Extended registration form that collects all university fields.
    """

    first_name    = forms.CharField(max_length=100, required=False, label='Full Name')
    email         = forms.EmailField(required=True,  label='University Email')
    university    = forms.CharField(max_length=200,  required=False, label='University')
    department    = forms.CharField(max_length=200,  required=False, label='Faculty / Department')
    student_id    = forms.CharField(max_length=50,   required=False, label='Student ID')
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
            'university', 'department', 'student_id', 'year_of_study',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email         = self.cleaned_data['email']
        user.first_name    = self.cleaned_data.get('first_name', '')
        user.university    = self.cleaned_data.get('university', '')
        user.department    = self.cleaned_data.get('department', '')
        user.student_id    = self.cleaned_data.get('student_id', '')
        user.year_of_study = self.cleaned_data.get('year_of_study', '')
        user.role          = 'student'  # Default all new registrations to student
        if commit:
            user.save()
        return user
