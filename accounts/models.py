from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        SOCIETY = 'society', 'Society / Club'
        STAFF   = 'staff',   'Staff'
        ADMIN   = 'admin',   'Admin'

    class Plan(models.TextChoices):
        FREE    = 'free',    'Free'
        PREMIUM = 'premium', 'Premium'

    class YearOfStudy(models.TextChoices):
        YEAR_1 = '1',  'Year 1 — Fresher'
        YEAR_2 = '2',  'Year 2'
        YEAR_3 = '3',  'Year 3'
        YEAR_4 = '4',  'Year 4'
        YEAR_5 = '5',  'Year 5'
        PG     = 'pg', 'Postgraduate'
        PHD    = 'phd','PhD'

    # ── Contact & identity ────────────────
    email           = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio             = models.TextField(blank=True)
    phone_number    = models.CharField(max_length=20, blank=True)

    # ── University info ───────────────────
    university      = models.CharField(max_length=200, blank=True)
    department      = models.CharField(max_length=200, blank=True)
    student_id      = models.CharField(max_length=50,  blank=True)
    year_of_study   = models.CharField(
        max_length=5,
        choices=YearOfStudy.choices,
        blank=True,
    )

    # ── Role & plan ───────────────────────
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.FREE,
    )
    plan_expiry = models.DateTimeField(blank=True, null=True)

    # ── Timestamps ────────────────────────
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name        = 'User'
        verbose_name_plural = 'Users'
        ordering            = ['-date_joined']

    def __str__(self):
        return f'{self.username} ({self.email})'

    @property
    def is_organiser(self):
        return self.role in [self.Role.SOCIETY, self.Role.STAFF, self.Role.ADMIN]

    @property
    def display_university(self):
        return self.university or 'University not set'

    @property
    def display_year(self):
        if not self.year_of_study:
            return ''
        return dict(self.YearOfStudy.choices).get(self.year_of_study, '')
