from django.db import models
from django.conf import settings
from django.utils import timezone


class Subscription(models.Model):
    """
    Tracks a user's active Stripe subscription.
    Updated via Stripe webhooks — never write to this manually.
    """

    class Plan(models.TextChoices):
        PREMIUM_MONTHLY = "premium_monthly", "Premium Monthly"
        PREMIUM_YEARLY = "premium_yearly", "Premium Yearly"
        ORGANISER_MONTHLY = "organiser_monthly", "Organiser Pro Monthly"
        ORGANISER_YEARLY = "organiser_yearly", "Organiser Pro Yearly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        PAST_DUE = "past_due", "Past Due"
        TRIALING = "trialing", "Trialing"
        INCOMPLETE = "incomplete", "Incomplete"
        EXPIRED = "expired", "Expired"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    # Stripe IDs
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    stripe_subscription_id = models.CharField(max_length=100, unique=True)

    # Plan details
    plan = models.CharField(max_length=30, choices=Plan.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.INCOMPLETE
    )

    # Dates
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        return f"{self.user.username} — {self.plan} [{self.status}]"

    @property
    def is_active(self):
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class PaymentRecord(models.Model):
    """
    A log of each individual payment (Stripe PaymentIntent / Invoice).
    Created from Stripe webhooks. Used for receipts and revenue analytics.
    """

    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_records",
    )

    # Stripe references
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)

    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Payment Record"
        verbose_name_plural = "Payment Records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.amount} {self.currency} [{self.status}]"
