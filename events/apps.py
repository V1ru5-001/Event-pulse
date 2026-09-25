from django.apps import AppConfig


class EventsConfig(AppConfig):
    # Matches the existing tables (see migration 0002); Django 6 would
    # otherwise default to BigAutoField and try to migrate every PK.
    default_auto_field = 'django.db.models.AutoField'
    name = 'events'

    def ready(self):
        import events.signals  # noqa: F401