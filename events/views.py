from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Q, Count
import calendar as pycal
import os
import re
import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.files import File
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Event, Category, RSVP, EventMedia
from .validators import MAX_VIDEO_SIZE, classify_media_name, validate_media_size


def landing_view(request):
    """Public landing page — shown to everyone not logged in."""
    if request.user.is_authenticated:
        return redirect('events:home')

    events = Event.objects.filter(
        status=Event.Status.PUBLISHED
    ).select_related('organiser', 'category').annotate(
        approved_count=Count('rsvps', filter=Q(rsvps__status=RSVP.Status.APPROVED))
    ).order_by('-is_featured', '-created_at')[:6]

    from django.contrib.auth import get_user_model
    User = get_user_model()
    stats = {
        'students':  User.objects.filter(role='student').count(),
        'events':    Event.objects.filter(status=Event.Status.PUBLISHED).count(),
        'societies': User.objects.filter(role='society').count(),
    }

    return render(request, 'events/landing.html', {'events': events, 'stats': stats})


@login_required(login_url='accounts:login')
def home_view(request):
    """Main event feed — authenticated users only."""
    query    = request.GET.get('q', '').strip()
    category = request.GET.get('cat', '').strip()
    now      = timezone.now()

    events = Event.objects.filter(
        status=Event.Status.PUBLISHED
    ).select_related('organiser', 'category').annotate(
        approved_count=Count('rsvps', filter=Q(rsvps__status=RSVP.Status.APPROVED))
    ).order_by('-is_featured', '-created_at')

    # ── Search — title matched first ──────────
    if query:
        events = events.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location_name__icontains=query) |
            Q(location_address__icontains=query) |
            Q(organiser__username__icontains=query) |
            Q(organiser__first_name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(area__icontains=query)
        )

    # ── Category filter ───────────────────────
    if category and category != 'all':
        events = events.filter(category__slug=category)

    return render(request, 'events/home.html', {
        'events':     events,
        'query':      query,
        'active_cat': category,
        'now':        now,
    })


@login_required(login_url='accounts:login')
def create_event_view(request, slug=None):
    categories = Category.objects.all().order_by('name')

    # ── Edit mode: load existing event ────────
    event = None
    if slug:
        event = get_object_or_404(Event, slug=slug, organiser=request.user)

    if request.method == 'POST':
        title        = request.POST.get('title', '').strip()
        description  = request.POST.get('description', '').strip()
        category_id  = request.POST.get('category', '')
        location     = request.POST.get('location_name', '').strip()
        start_dt     = request.POST.get('start_datetime', '')
        end_dt       = request.POST.get('end_datetime', '') or None
        price_type   = request.POST.get('price_type', 'free')
        ticket_price = request.POST.get('ticket_price', 0) or 0
        capacity     = request.POST.get('capacity', '') or None
        is_premium   = request.POST.get('is_premium_only', 'false') == 'true'
        require_approval = request.POST.get('require_rsvp_approval', 'false') == 'true'
        redirect_url = request.POST.get('rsvp_redirect_url', '').strip() or None
        action       = request.POST.get('action', 'publish')
        gallery_keys     = request.POST.getlist('gallery_keys')
        remove_media_ids = request.POST.getlist('remove_gallery')

        if not title or not description or not location or not start_dt:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'events/create_event.html', {
                'categories': categories, 'event': event
            })

        if redirect_url:
            # Attendees get sent here, so only allow ordinary web links.
            try:
                URLValidator(schemes=['http', 'https'])(redirect_url)
            except ValidationError:
                messages.error(request, 'The RSVP redirect link must be a full http:// or https:// URL.')
                return render(request, 'events/create_event.html', {
                    'categories': categories, 'event': event
                })

        try:
            classified_media = [
                (key, _validate_uploaded_gallery_key(request.user, key))
                for key in gallery_keys
            ]
        except ValidationError as e:
            messages.error(request, e.message)
            return render(request, 'events/create_event.html', {
                'categories': categories, 'event': event
            })

        # ── Resolve category ──────────────────
        category = None
        if category_id:
            try:
                if str(category_id).isdigit():
                    category = Category.objects.get(pk=category_id)
                else:
                    slug_to_name = {
                        'academic':      ('Academic',),
                        'social':        ('Social',),
                        'sports':        ('Sports',),
                        'career':        ('Career',),
                        'arts':          ('Arts & Culture',),
                        'music':         ('Music & Parties',),
                        'international': ('International',),
                    }
                    # clubs is not a valid category — never create it
                    if category_id in slug_to_name:
                        name = slug_to_name[category_id][0]
                        category, _ = Category.objects.get_or_create(
                            slug=category_id,
                            defaults={'name': name}
                        )
            except Category.DoesNotExist:
                pass

        status = Event.Status.PUBLISHED if action == 'publish' else Event.Status.DRAFT

        if event:
            # ── UPDATE existing event ─────────
            event.title            = title
            event.description      = description
            event.category         = category
            event.location_name    = location
            event.location_address = request.POST.get('location_address', '')
            event.start_datetime   = start_dt
            event.end_datetime     = end_dt
            event.price_type       = price_type
            event.ticket_price     = ticket_price
            event.capacity         = capacity
            event.is_premium_only  = is_premium
            event.require_rsvp_approval = require_approval
            event.rsvp_redirect_url     = redirect_url
            event.status           = status
            event.save()
            messages.success(request, f'"{event.title}" has been updated!')
            _notify_followers_new_event(event)
        else:
            # ── CREATE new event ──────────────
            event = Event(
                title            = title,
                description      = description,
                organiser        = request.user,
                category         = category,
                location_name    = location,
                location_address = request.POST.get('location_address', ''),
                start_datetime   = start_dt,
                price_type       = price_type,
                ticket_price     = ticket_price,
                capacity         = capacity,
                is_premium_only  = is_premium,
                require_rsvp_approval = require_approval,
                rsvp_redirect_url     = redirect_url,
                status           = status,
            )
            if end_dt:
                event.end_datetime = end_dt
            event.save()
            messages.success(request, f'"{event.title}" is now live!')
            _notify_followers_new_event(event)

        if remove_media_ids:
            removed = event.gallery.filter(id__in=remove_media_ids)
            for media in removed:
                media.file.delete(save=False)
            removed.delete()

        if classified_media:
            start_order = event.gallery.count()
            for i, (key, media_type) in enumerate(classified_media):
                # Assigning the storage key directly points the FileField at
                # the object the browser already uploaded — no bytes re-sent.
                EventMedia.objects.create(
                    event=event,
                    media_type=media_type,
                    file=key,
                    order=start_order + i,
                )

        if action == 'publish':
            return redirect('events:detail', slug=event.slug)
        else:
            messages.info(request, f'"{event.title}" saved as draft.')
            return redirect('accounts:profile', username=request.user.username)

    return render(request, 'events/create_event.html', {
        'categories': categories,
        'event':      event,
    })


# ── Direct-to-storage gallery uploads ─────────────────────
# Vercel functions cap request bodies at 4.5MB, so the browser uploads
# gallery files straight to the bucket and only sends Django the key.

def _gallery_prefix(user):
    return f'events/gallery/u{user.pk}/'


def _is_own_gallery_key(user, key):
    pattern = re.escape(_gallery_prefix(user)) + r'[0-9a-f]{32}\.[a-z0-9]{1,5}'
    return re.fullmatch(pattern, key) is not None


def _validate_uploaded_gallery_key(user, key):
    """Check a submitted key is this user's finished upload; return its media type."""
    if not _is_own_gallery_key(user, key):
        raise ValidationError('Invalid upload reference. Please re-add your files.')
    if EventMedia.objects.filter(file=key).exists():
        raise ValidationError('That file is already attached to an event. Please re-add your files.')
    if not default_storage.exists(key):
        raise ValidationError('A file upload did not finish. Please try again.')
    media_type = classify_media_name(key)
    try:
        validate_media_size(os.path.basename(key), media_type, default_storage.size(key))
    except ValidationError:
        default_storage.delete(key)
        raise
    return media_type


@login_required(login_url='accounts:login')
@require_POST
def presign_upload_view(request):
    filename     = request.POST.get('filename', '')
    content_type = request.POST.get('content_type', '')
    try:
        size = int(request.POST.get('size', '0'))
    except ValueError:
        size = 0

    try:
        media_type = classify_media_name(filename)
        validate_media_size(filename, media_type, size)
    except ValidationError as e:
        return JsonResponse({'error': e.message}, status=400)

    if not content_type.startswith(f'{media_type}/'):
        return JsonResponse({'error': f'"{filename}" has an unexpected file type.'}, status=400)

    ext = os.path.splitext(filename)[1].lower()
    key = f'{_gallery_prefix(request.user)}{uuid.uuid4().hex}{ext}'

    if settings.USE_S3:
        # Reuse django-storages' own boto3 client so endpoint/region/
        # credentials always match the working storage config.
        client = default_storage.connection.meta.client
        upload_url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket':      default_storage.bucket_name,
                'Key':         key,
                'ContentType': content_type,
            },
            ExpiresIn=600,
        )
    else:
        upload_url = reverse('events:local_upload', args=[key])

    return JsonResponse({'upload_url': upload_url, 'key': key})


@login_required(login_url='accounts:login')
def local_upload_view(request, key):
    """Stand-in for the presigned PUT when running without a bucket (local dev)."""
    if settings.USE_S3:
        raise Http404
    if request.method != 'PUT':
        return HttpResponseNotAllowed(['PUT'])
    if not _is_own_gallery_key(request.user, key):
        return JsonResponse({'error': 'Invalid upload key.'}, status=403)
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        length = 0
    if length <= 0 or length > MAX_VIDEO_SIZE:
        return JsonResponse({'error': 'File is empty or too large.'}, status=400)

    # Stream from the request rather than request.body, which is capped
    # by DATA_UPLOAD_MAX_MEMORY_SIZE (2.5MB).
    default_storage.save(key, File(request, name=key))
    return HttpResponse(status=204)


@login_required(login_url='accounts:login')
def delete_event_view(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f'"{title}" has been deleted.')
        return redirect('accounts:profile', username=request.user.username)
    return redirect('events:detail', slug=slug)


@login_required(login_url='accounts:login')
def event_detail_view(request, slug):
    event = get_object_or_404(Event, slug=slug)

    # check premium gate
    if event.is_premium_only and not request.user.is_premium:
        messages.warning(request, 'This event is for premium members only.')

    # get user's RSVP if any
    user_rsvp = None
    if request.user.is_authenticated:
        user_rsvp = RSVP.objects.filter(event=event, user=request.user).first()

    # ── event status flags (drives the RSVP button) ──
    now = timezone.now()
    start = event.start_datetime
    end   = event.end_datetime or start

    is_ended       = end < now
    is_live        = start <= now <= end
    is_coming_soon = start > now

    return render(request, 'events/event_detail.html', {
        'event':          event,
        'user_rsvp':      user_rsvp,
        'is_ended':       is_ended,
        'is_live':        is_live,
        'is_coming_soon': is_coming_soon,
    })

def profile_view(request, username):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    profile_user = get_object_or_404(User, username=username)
    is_own       = request.user.is_authenticated and request.user == profile_user

    posted_events = Event.objects.filter(
        organiser=profile_user,
        status=Event.Status.PUBLISHED
    ).order_by('-created_at')

    draft_events = Event.objects.none()
    accepted_guests = (
        RSVP.objects.filter(
            event__organiser=profile_user,
            status=RSVP.Status.APPROVED,
        )
        .select_related('user', 'event')
        .order_by('-joined_at')
    )

    if is_own:
        draft_events = Event.objects.filter(
            organiser=profile_user,
            status=Event.Status.DRAFT
        ).order_by('-updated_at')

        attending_events = RSVP.objects.filter(
            user=profile_user
        ).select_related('event').order_by('-joined_at')

    rsvp_count = RSVP.objects.filter(
        event__organiser=profile_user,
        status=RSVP.Status.APPROVED
    ).count()

    viewer_is_following = (
        request.user.is_authenticated
        and not is_own
        and request.user.is_following(profile_user)
    )

    return render(request, 'accounts/profile.html', {
        'profile_user':    profile_user,
        'posted_events':   posted_events,
        'draft_events':    draft_events,
        'accepted_guests': accepted_guests,
        'rsvp_count':      rsvp_count,
        'is_own_profile':  is_own,
        'viewer_is_following': viewer_is_following,
    })
@login_required(login_url='accounts:login')
def rsvp_view(request, slug):
    from .models import RSVP
    if request.method != 'POST':
        return redirect('events:detail', slug=slug)

    event  = get_object_or_404(Event, slug=slug)
    note   = request.POST.get('note', '')

    # check existing RSVP
    existing = RSVP.objects.filter(event=event, user=request.user).first()

    if existing:
        messages.info(request, 'You have already submitted a request for this event.')
        return redirect('events:detail', slug=slug)

    # Capacity is the authority on waitlisting; otherwise the organiser's
    # setting decides between instant approval and manual review.
    if event.is_full:
        status = RSVP.Status.WAITLIST
        msg    = "You have been added to the waitlist."
    elif event.require_rsvp_approval:
        status = RSVP.Status.PENDING
        msg    = "Your RSVP request has been sent to the organiser."
    else:
        status = RSVP.Status.APPROVED
        msg    = "You're in! Your RSVP has been approved."

    RSVP.objects.create(
        event  = event,
        user   = request.user,
        status = status,
        note   = note,
    )

    from social.models import Notification

    Notification.objects.create(
        recipient = event.organiser,
        actor     = request.user,
        event     = event,
        kind      = Notification.Kind.RSVP_REQUEST,
        note      = note,
    )

    # Manual approvals notify the attendee from manage_rsvps_view instead.
    if status == RSVP.Status.APPROVED:
        Notification.objects.create(
            recipient = request.user,
            actor     = event.organiser,
            event     = event,
            kind      = Notification.Kind.RSVP_APPROVED,
            note      = '',
        )

    messages.success(request, msg)

    if status == RSVP.Status.APPROVED and event.rsvp_redirect_url:
        return redirect(event.rsvp_redirect_url)
    return redirect('events:detail', slug=slug)
@login_required(login_url='accounts:login')
def manage_rsvps_view(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    rsvps = RSVP.objects.filter(event=event).select_related('user').order_by('-joined_at')

    if request.method == 'POST':
        rsvp_id = request.POST.get('rsvp_id')
        action  = request.POST.get('action')
        try:
            rsvp = RSVP.objects.get(pk=rsvp_id, event=event)
            if action == 'approve':
                rsvp.status = RSVP.Status.APPROVED
                rsvp.save()
                from social.models import Notification
                Notification.objects.create(
                    recipient = rsvp.user,
                    actor     = request.user,
                    event     = event,
                    kind      = Notification.Kind.RSVP_APPROVED,
                )
                messages.success(request, f'{rsvp.user.username} has been approved.')
            elif action == 'reject':
                rsvp.status = RSVP.Status.REJECTED
                rsvp.save()
                messages.info(request, f'{rsvp.user.username} has been rejected.')
        except RSVP.DoesNotExist:
            pass
        return redirect('events:manage_rsvps', slug=slug)

    return render(request, 'events/manage_rsvps.html', {
        'event': event,
        'rsvps': rsvps,
         'approved_count': rsvps.filter(status=RSVP.Status.APPROVED).count(),
    })
# ═══════════════════════════════════════════════════════════
# ADD TO: events/views.py
#
# 1. Add these two imports at the TOP of the file with the others:
#      import calendar as pycal
#      from datetime import date
#    (timezone is already imported)
#
# 2. Paste the view below anywhere after home_view.
#
# 3. ADD TO events/urls.py, inside urlpatterns (before any
#    slug-catching patterns like <slug:slug>/):
#      path('calendar/', views.calendar_view, name='calendar'),
# ═══════════════════════════════════════════════════════════

@login_required(login_url='accounts:login')
def calendar_view(request):
    """Campus Calendar — month grid of all published events."""
    today = timezone.localdate()

    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        date(year, month, 1)  # validates the pair
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # clamp to a sane window so ?year=99999 can't run wild
    if year < today.year - 1 or year > today.year + 2:
        year, month = today.year, today.month

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    events = (
        Event.objects
        .filter(
            status=Event.Status.PUBLISHED,
            start_datetime__year=year,
            start_datetime__month=month,
        )
        .select_related('category', 'organiser')
        .order_by('start_datetime')
    )

    events_by_day = {}
    for e in events:
        d = timezone.localtime(e.start_datetime).day
        events_by_day.setdefault(d, []).append(e)

    cal = pycal.Calendar(firstweekday=0)  # weeks start Monday
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        row = []
        for d in week:
            row.append({
                'day': d,  # 0 = padding cell outside this month
                'events': events_by_day.get(d, []),
                'is_today': (
                    d == today.day and month == today.month and year == today.year
                ),
            })
        weeks.append(row)

    return render(request, 'events/calendar.html', {
        'weeks':        weeks,
        'year':         year,
        'month':        month,
        'month_name':   date(year, month, 1).strftime('%B'),
        'prev_y':       prev_y, 'prev_m': prev_m,
        'next_y':       next_y, 'next_m': next_m,
        'is_current_month': (year == today.year and month == today.month),
        'month_events': events,
    })
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