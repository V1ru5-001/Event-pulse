from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db.models import Q, Max

from .models import Follow, Conversation, Message

User = get_user_model()


# ── Follows ───────────────────────────────
@login_required(login_url='accounts:login')
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        messages.error(request, "You can't follow yourself.")
        return redirect('accounts:profile', username=username)

    existing = Follow.objects.filter(follower=request.user, following=target).first()
    if existing:
        existing.delete()
        followed = False
    else:
        Follow.objects.create(follower=request.user, following=target)
        followed = True

    # AJAX support
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'followed': followed,
            'followers_count': target.followers_count,
        })

    return redirect('accounts:profile', username=username)


@login_required(login_url='accounts:login')
def follow_list(request, username, mode):
    """mode = 'followers' or 'following'"""
    profile_user = get_object_or_404(User, username=username)
    if mode == 'followers':
        qs = User.objects.filter(following_set__following=profile_user)
        title = 'Followers'
    else:
        qs = User.objects.filter(follower_set__follower=profile_user)
        title = 'Following'

    return render(request, 'social/follow_list.html', {
        'profile_user': profile_user,
        'people':       qs,
        'list_title':   title,
        'mode':         mode,
    })


# ── Chat ──────────────────────────────────
@login_required(login_url='accounts:login')
def inbox(request):
    convos = (
        request.user.conversations
        .prefetch_related('participants', 'messages')
        .annotate(last=Max('messages__created_at'))
        .order_by('-last')
    )
    # Build lightweight view objects
    threads = []
    for c in convos:
        other = c.other_participant(request.user)
        if other is None:
            continue
        last = c.last_message
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        threads.append({
            'conversation': c,
            'other':        other,
            'last_message': last,
            'unread':       unread,
        })

    return render(request, 'social/inbox.html', {'threads': threads})


@login_required(login_url='accounts:login')
def start_conversation(request, username):
    """Open (or create) a conversation with a user, then redirect to it."""
    other = get_object_or_404(User, username=username)
    if other == request.user:
        messages.error(request, "You can't message yourself.")
        return redirect('social:inbox')

    convo, _ = Conversation.get_or_create_between(request.user, other)
    return redirect('social:conversation', pk=convo.pk)


@login_required(login_url='accounts:login')
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation, pk=pk, participants=request.user)
    other = convo.other_participant(request.user)

    # Mark incoming messages as read
    convo.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    msg_list = convo.messages.select_related('sender').all()

    return render(request, 'social/conversation.html', {
        'conversation': convo,
        'other':        other,
        'messages_list': msg_list,
    })


@login_required(login_url='accounts:login')
@require_POST
def send_message(request, pk):
    convo = get_object_or_404(Conversation, pk=pk, participants=request.user)
    body = (request.POST.get('body') or '').strip()
    if not body:
        return HttpResponseBadRequest('Empty message')

    msg = Message.objects.create(conversation=convo, sender=request.user, body=body)
    convo.save()  # bump updated_at

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'id':      msg.id,
            'body':    msg.body,
            'sender':  msg.sender.username,
            'created': msg.created_at.strftime('%H:%M'),
            'mine':    True,
        })

    return redirect('social:conversation', pk=pk)


@login_required(login_url='accounts:login')
def fetch_messages(request, pk):
    """Polling endpoint: return messages after a given id as JSON."""
    convo = get_object_or_404(Conversation, pk=pk, participants=request.user)
    after_id = request.GET.get('after', 0)
    try:
        after_id = int(after_id)
    except (TypeError, ValueError):
        after_id = 0

    new_msgs = convo.messages.select_related('sender').filter(id__gt=after_id)

    # Mark the ones from the other person as read
    convo.messages.filter(id__gt=after_id, is_read=False).exclude(sender=request.user).update(is_read=True)

    data = [{
        'id':      m.id,
        'body':    m.body,
        'sender':  m.sender.username,
        'created': m.created_at.strftime('%H:%M'),
        'mine':    m.sender_id == request.user.id,
    } for m in new_msgs]

    return JsonResponse({'messages': data})
