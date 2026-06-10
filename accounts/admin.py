from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    list_display  = ['username', 'email', 'university', 'year_of_study', 'role', 'plan', 'date_joined']
    list_filter   = ['role', 'plan', 'year_of_study', 'university']
    search_fields = ['username', 'email', 'first_name', 'university', 'student_id']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('University Info', {
            'fields': ('university', 'department', 'student_id', 'year_of_study'),
        }),
        ('Role & Plan', {
            'fields': ('role', 'plan', 'plan_expiry'),
        }),
        ('Profile', {
            'fields': ('bio', 'profile_picture', 'phone_number'),
        }),
    )
