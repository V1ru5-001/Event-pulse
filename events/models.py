import uuid
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings


class Category(models.Model):
    name        = models.CharField(max_length=60, unique=True)
    slug        = models.SlugField(max_length=60, unique=True, blank=True)
    icon        = models.CharField(max_length=10, blank=True, help_text="Emoji e.g. 🎵")
    description = models.TextField(blank=True)
    colour      = models.CharField(max_length=7, default="#4B6BF1", help_text="Hex colour for UI badges")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Category"
        verbose_name_plural = "Categories"
        ordering            = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.icon} {self.name}".strip()


class Event(models.Model):

    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    class PriceType(models.TextChoices):
        FREE = "free", "Free"
        PAID = "paid", "Paid"

    # ── Core info ────────────────────────────
    title       = models.CharField(max_length=200)
    slug        = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    cover_image = models.ImageField(upload_to="events/covers/", blank=True, null=True)

    # ── Relations ────────────────────────────
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organised_events",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    # ── Location ─────────────────────────────
    location_name    = models.CharField(max_length=200)
    location_address = models.TextField(blank=True)
    location_lat     = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    location_lng     = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    area             = models.CharField(max_length=100, blank=True, help_text="Neighbourhood or city for filtering")

    # ── Date & time ───────────────────────────
    start_datetime = models.DateTimeField()
    end_datetime   = models.DateTimeField(blank=True, null=True)

    # ── Capacity & pricing ────────────────────
    capacity     = models.PositiveIntegerField(blank=True, null=True, help_text="Leave blank for unlimited")
    price_type   = models.CharField(max_length=10, choices=PriceType.choices, default=PriceType.FREE)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # ── Visibility flags ──────────────────────
    is_premium_only = models.BooleanField(default=False, help_text="Only premium users can join")
    is_featured     = models.BooleanField(default=False, help_text="Pin to top of feed")
    status          = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # ── QR attendance ─────────────────────────
    checkin_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Embedded in QR code for check-in",
    )
    qr_code = models.ImageField(
        upload_to="qrcodes/",
        blank=True,
        null=True,
        help_text="Auto-generated on publish",
    )

    # ── Timestamps ────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Event"
        verbose_name_plural = "Events"
        ordering            = ["-is_featured", "-created_at"]
        indexes = [
            models.Index(fields=["status", "start_datetime"]),
            models.Index(fields=["organiser"]),
            models.Index(fields=["category"]),
            models.Index(fields=["area"]),
        ]

    # ── Auto slug ─────────────────────────────
    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n    = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n   += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    # ── Convenience properties ────────────────
    @property
    def is_past(self):
        if self.end_datetime:
            return self.end_datetime < timezone.now()
        return self.start_datetime < timezone.now()

    @property
    def approved_rsvp_count(self):
        return self.rsvps.filter(status=RSVP.Status.APPROVED).count()

    @property
    def is_full(self):
        if self.capacity is None:
            return False
        return self.approved_rsvp_count >= self.capacity

    @property
    def spots_remaining(self):
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.approved_rsvp_count)

    @property
    def checkin_url(self):
        return f"/events/{self.slug}/checkin/?token={self.checkin_token}"

    @property
    def attendance_count(self):
        return self.attendances.count()

    @property
    def is_free(self):
        return self.price_type == self.PriceType.FREE or self.ticket_price == 0


class RSVP(models.Model):

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        APPROVED  = "approved",  "Approved"
        REJECTED  = "rejected",  "Rejected"
        WAITLIST  = "waitlist",  "Waitlist"
        CANCELLED = "cancelled", "Cancelled"

    event     = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rsvps")
    status    = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    note      = models.TextField(blank=True, help_text="Optional message to the organiser")
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = ("event", "user")
        verbose_name        = "RSVP"
        verbose_name_plural = "RSVPs"
        ordering            = ["-joined_at"]

    def __str__(self):
        return f"{self.user.username} → {self.event.title} [{self.status}]"


class Attendance(models.Model):
    """Created when an approved user scans the event QR code at the door."""

    event         = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendances")
    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendances")
    checked_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ("event", "user")
        verbose_name        = "Attendance"
        verbose_name_plural = "Attendances"
        ordering            = ["-checked_in_at"]

    def __str__(self):
        return f"{self.user.username} checked into {self.event.title}"


class Review(models.Model):

    event      = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reviews")
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating     = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    body       = models.TextField()
    is_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = ("event", "author")
        verbose_name        = "Review"
        verbose_name_plural = "Reviews"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.author.username} — {self.event.title} ({self.rating}★)"


class ReviewReply(models.Model):
    """Organiser reply to a single review."""

    review     = models.OneToOneField(Review, on_delete=models.CASCADE, related_name="reply")
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_replies")
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Review Reply"
        verbose_name_plural = "Review Replies"

    def __str__(self):
        return f"Reply to review #{self.review.pk} by {self.author.username}"
