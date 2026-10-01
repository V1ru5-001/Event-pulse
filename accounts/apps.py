from django.apps import AppConfig


class AccountsConfig(AppConfig):
    # Matches the existing table (see migration 0003); Django 6 would
    # otherwise default to BigAutoField and try to migrate the PK.
    default_auto_field = 'django.db.models.AutoField'
    name = 'accounts'
