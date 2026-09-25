"""
signals.py  (events app)

Wire these up in events/apps.py:

    class EventsConfig(AppConfig):
        name = "events"
        def ready(self):
            import events.signals  # noqa
"""

import io
import qrcode
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.files.base import ContentFile

from .models import Event, RSVP, EventMedia


# ─── QR Code generation ──────────────────────────────────────────────────────

@receiver(post_save, sender=Event)
def generate_event_qr(sender, instance, created, **kwargs):
    """
    Auto-generate a QR code when an event is first published.
    The QR encodes the check-in URL: /events/<slug>/checkin/?token=<uuid>
    Skips if the QR already exists to avoid infinite save loop.
    """
    if instance.status == Event.Status.PUBLISHED and not instance.qr_code:
        # Build the check-in URL
        checkin_url = (
            f"https://eventpulse.com/events/{instance.slug}"
            f"/checkin/?token={instance.checkin_token}"
        )

        # Generate QR image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(checkin_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to an in-memory buffer, then to the ImageField
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        filename = f"event_{instance.pk}.png"

        # Use update_fields to avoid triggering this signal again
        instance.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
        Event.objects.filter(pk=instance.pk).update(qr_code=instance.qr_code)


# ─── Storage cleanup on delete ────────────────────────────────────────────────
# Deletes the actual files in storage (Supabase/S3) whenever an Event or
# EventMedia row is deleted from the database — otherwise Django only removes
# the DB row and the file sits orphaned in the bucket forever, still counting
# against your storage quota.
#
# post_delete fires for every row Django's CASCADE collector removes, so this
# also cleans up EventMedia files automatically when their parent Event is
# deleted, not just on a direct EventMedia delete.

def _delete_file_field(field_file):
    """Delete a single FileField/ImageField's underlying file, if it has one."""
    if field_file and field_file.name:
        field_file.storage.delete(field_file.name)


@receiver(post_delete, sender=Event)
def delete_event_files(sender, instance, **kwargs):
    _delete_file_field(instance.cover_image)
    _delete_file_field(instance.qr_code)


@receiver(post_delete, sender=EventMedia)
def delete_event_media_file(sender, instance, **kwargs):
    _delete_file_field(instance.file)