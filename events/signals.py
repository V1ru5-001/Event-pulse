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
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile

from .models import Event, RSVP


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


# ─── RSVP notifications ───────────────────────────────────────────────────────

@receiver(post_save, sender=RSVP)
def notify_on_rsvp_change(sender, instance, created, **kwargs):
    """
    Send in-app notifications when RSVP status changes.
    - New RSVP → notify organiser
    - Approved / Rejected → notify attendee
    - Promoted from waitlist → notify attendee
    """
    from core.models import Notification  # avoid circular import

    if created:
        # Notify organiser of new RSVP request
        Notification.objects.create(
            recipient=instance.event.organiser,
            notification_type=Notification.Type.RSVP_RECEIVED,
            title="New RSVP Request",
            message=f"{instance.user.username} wants to join {instance.event.title}.",
            link=f"/dashboard/events/{instance.event.slug}/rsvps/",
        )
        return

    # Status update notifications sent to the attendee
    status_map = {
        RSVP.Status.APPROVED: (
            Notification.Type.RSVP_APPROVED,
            "RSVP Approved!",
            f"You have been approved to attend {instance.event.title}.",
        ),
        RSVP.Status.REJECTED: (
            Notification.Type.RSVP_REJECTED,
            "RSVP Not Approved",
            f"Your request for {instance.event.title} was not approved.",
        ),
        RSVP.Status.WAITLIST: (
            Notification.Type.WAITLIST_PROMOTED,
            "You're on the Waitlist",
            f"You have been added to the waitlist for {instance.event.title}.",
        ),
    }

    if instance.status in status_map:
        n_type, title, message = status_map[instance.status]
        Notification.objects.create(
            recipient=instance.user,
            notification_type=n_type,
            title=title,
            message=message,
            link=f"/events/{instance.event.slug}/",
        )
