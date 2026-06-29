"""
social/context_processors.py
Makes the unread-message count available on every page (for the navbar badge).
Add 'social.context_processors.unread_messages' to TEMPLATES['OPTIONS']['context_processors'].
"""
from social.models import Message


def unread_messages(request):
    if not request.user.is_authenticated:
        return {'unread_messages_count': 0}

    count = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return {'unread_messages_count': count}
