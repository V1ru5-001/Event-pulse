from django.db import models
from django.conf import settings
from django.db.models import Q


class Follow(models.Model):
    """One-way follow relationship (like X / Twitter)."""
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following_set',
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='follower_set',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['follower', 'following'],
                name='unique_follow',
            ),
            models.CheckConstraint(
                check=~Q(follower=models.F('following')),
                name='no_self_follow',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.follower} → {self.following}'


class Conversation(models.Model):
    """A 1-to-1 conversation between exactly two users."""
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        names = ', '.join(u.username for u in self.participants.all())
        return f'Conversation ({names})'

    def other_participant(self, user):
        """Return the participant who is not `user`."""
        return self.participants.exclude(pk=user.pk).first()

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()

    @staticmethod
    def get_or_create_between(user_a, user_b):
        """Find the existing 1:1 conversation between two users, or create it."""
        existing = (
            Conversation.objects
            .filter(participants=user_a)
            .filter(participants=user_b)
            .first()
        )
        if existing:
            return existing, False
        convo = Conversation.objects.create()
        convo.participants.add(user_a, user_b)
        return convo, True


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.body[:30]}'
# ═══════════════════════════════════════════════════════════
# NOTIFICATIONS — "someone you follow posted an event"
# Four small edits, in this order. Then run:
#   python manage.py makemigrations social
#   python manage.py migrate
# and restart the dev server.
# ═══════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# 1) ADD TO THE BOTTOM OF: social/models.py
# ─────────────────────────────────────────────

class Notification(models.Model):
    """In-app notification. v1 covers one kind: a followed user
    published an event. `kind` is a choices field so more types
    (rsvp_approved, event_reminder, new_follower) slot in later
    without a schema change."""

    class Kind(models.TextChoices):
        NEW_EVENT     = 'new_event',     'New event from someone you follow'
        RSVP_REQUEST  = 'rsvp_request',  'Someone requested to join your event'
        RSVP_APPROVED = 'rsvp_approved', 'Your request to join was approved'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
    )
    kind = models.CharField(
        max_length=30,
        choices=Kind.choices,
        default=Kind.NEW_EVENT,
    )
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True, blank=True,
    )
    note = models.CharField(max_length=500, blank=True, default='')
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f'{self.recipient} ← {self.kind} ({self.actor})'


# ─────────────────────────────────────────────
# 2) ADD TO: events/views.py
#    Paste this helper anywhere above create_event_view.
# ─────────────────────────────────────────────

def _notify_followers_new_event(event):
    """Create one notification per follower of the organiser.
    Safe to call multiple times: fires once per event ever
    (so editing a published event never re-notifies)."""
    from social.models import Notification

    if event.status != Event.Status.PUBLISHED:
        return
    if Notification.objects.filter(
        event=event, kind=Notification.Kind.NEW_EVENT
    ).exists():
        return

    follower_ids = event.organiser.follower_set.values_list(
        'follower_id', flat=True
    )
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=uid,
                actor=event.organiser,
                event=event,
                kind=Notification.Kind.NEW_EVENT,
            )
            for uid in follower_ids
        ],
        batch_size=500,
    )


# ─────────────────────────────────────────────
# 2b) STILL IN events/views.py — call the helper.
#     In create_event_view there are two `event.save()` calls
#     (UPDATE branch and CREATE branch). Add this line
#     IMMEDIATELY AFTER EACH of the two saves:
#
#         event.save()
#         _notify_followers_new_event(event)   # ← add this
#
#     The helper no-ops for drafts and dedupes for edits, so a
#     draft that gets published later notifies exactly once, at
#     publish time.
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 3) ADD TO THE BOTTOM OF: social/views.py
#    (login_required, render, redirect, get_object_or_404 are
#    already imported there; JsonResponse may need adding:
#      from django.http import JsonResponse )
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 4) ADD TO: social/urls.py — inside urlpatterns:
# ─────────────────────────────────────────────
#
#     # Notifications
#     path('notifications/',                  views.notifications_view,         name='notifications'),
#     path('notifications/<int:pk>/open/',    views.notification_open,          name='notification_open'),
#     path('notifications/read-all/',         views.notifications_read_all,     name='notifications_read_all'),
#     path('notifications/unread-count/',     views.notifications_unread_count, name='notifications_unread_count'),
#
# Also make sure social/models.py imports at the top include
# `settings` — it already does (`from django.conf import settings`).