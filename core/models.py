from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    In-app notification for a user.
    Covers RSVP updates, new reviews, event reminders, and system alerts.
    """

    class Type(models.TextChoices):
        RSVP_APPROVED = "rsvp_approved", "RSVP Approved"
        RSVP_REJECTED = "rsvp_rejected", "RSVP Rejected"
        RSVP_RECEIVED = "rsvp_received", "New RSVP Received"
        WAITLIST_PROMOTED = "waitlist_promoted", "Promoted from Waitlist"
        EVENT_REMINDER = "event_reminder", "Event Reminder"
        EVENT_CANCELLED = "event_cancelled", "Event Cancelled"
        NEW_REVIEW = "new_review", "New Review"
        NEW_FOLLOWER = "new_follower", "New Follower"
        PLAN_EXPIRING = "plan_expiring", "Plan Expiring Soon"
        PLAN_EXPIRED = "plan_expired", "Plan Expired"
        SYSTEM = "system", "System Alert"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=150)
    message = models.TextField()

    # Optional link to the relevant object
    link = models.CharField(max_length=300, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self):
        return f"[{self.notification_type}] → {self.recipient.username}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read"])
