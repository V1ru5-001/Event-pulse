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