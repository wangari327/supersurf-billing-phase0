from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from .money import format_ksh

MAX_MONEY_MINOR = 2_147_483_647


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    download_speed_mbps = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="KES", editable=False)
    duration_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    grace_period_hours = models.PositiveIntegerField(default=24)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Package"
        verbose_name_plural = "Packages"
        ordering = ["download_speed_mbps", "price_minor", "name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="billing_plan_name_ci_unique"),
            models.CheckConstraint(
                condition=Q(download_speed_mbps__gt=0),
                name="billing_plan_download_speed_positive",
            ),
            models.CheckConstraint(
                condition=Q(price_minor__gt=0),
                name="billing_plan_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="billing_plan_currency_kes",
            ),
            models.CheckConstraint(
                condition=Q(duration_days__gt=0),
                name="billing_plan_duration_positive",
            ),
            models.CheckConstraint(
                condition=Q(grace_period_hours__gte=0),
                name="billing_plan_grace_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.name = self.name.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Package name is required."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Package currency must be KES."})
        if self.price_minor is not None and self.price_minor <= 0:
            raise ValidationError({"price_minor": "Package price must be greater than zero."})
        if self.download_speed_mbps is not None and self.download_speed_mbps <= 0:
            raise ValidationError(
                {"download_speed_mbps": "Download speed must be greater than zero."}
            )
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValidationError({"duration_days": "Duration must be greater than zero."})
        if self.grace_period_hours is not None and self.grace_period_hours < 0:
            raise ValidationError(
                {"grace_period_hours": "Grace period cannot be negative."}
            )

    @property
    def formatted_price(self) -> str:
        return format_ksh(self.price_minor)


class SubscriptionQuerySet(models.QuerySet):
    immutable_update_fields = frozenset(
        {
            "service",
            "service_id",
            "plan",
            "plan_id",
            "starts_at",
            "plan_name",
            "download_speed_mbps",
            "price_minor",
            "currency",
            "duration_days",
            "grace_period_hours",
        }
    )
    lifecycle_update_fields = frozenset({"status", "ended_at"})

    def _reject_protected_updates(self, fields) -> None:
        requested = {str(field) for field in fields}
        protected = requested.intersection(
            self.immutable_update_fields | self.lifecycle_update_fields
        )
        if protected:
            names = ", ".join(sorted(protected))
            msg = f"Subscription field updates are not allowed through bulk paths: {names}."
            raise RuntimeError(msg)

    def update(self, **kwargs):
        self._reject_protected_updates(kwargs.keys())
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        self._reject_protected_updates(fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def delete(self):
        msg = "Subscriptions cannot be deleted through application code."
        raise RuntimeError(msg)


class SubscriptionManager(models.Manager):
    def get_queryset(self):
        return SubscriptionQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        self.get_queryset()._reject_protected_updates(fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)


class Subscription(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
    ]
    IMMUTABLE_FIELDS = (
        "service_id",
        "plan_id",
        "starts_at",
        "plan_name",
        "download_speed_mbps",
        "price_minor",
        "currency",
        "duration_days",
        "grace_period_hours",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "subscribers.Service",
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    starts_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    plan_name = models.CharField(max_length=120)
    download_speed_mbps = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="KES", editable=False)
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    grace_period_hours = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionManager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["service", "status"], name="billing_sub_service_status_idx"),
            models.Index(fields=["created_at"], name="billing_sub_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["service"],
                condition=Q(status="active"),
                name="billing_subscription_one_active_per_service",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["active", "ended"]),
                name="billing_subscription_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="active", ended_at__isnull=True)
                    | Q(status="ended", ended_at__isnull=False)
                ),
                name="billing_subscription_status_ended_at_consistent",
            ),
            models.CheckConstraint(
                condition=Q(price_minor__gt=0),
                name="billing_subscription_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(download_speed_mbps__gt=0),
                name="billing_subscription_download_positive",
            ),
            models.CheckConstraint(
                condition=Q(duration_days__gt=0),
                name="billing_subscription_duration_positive",
            ),
            models.CheckConstraint(
                condition=Q(grace_period_hours__gte=0),
                name="billing_subscription_grace_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="billing_subscription_currency_kes",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service} {self.plan_name}"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.plan_name = self.plan_name.strip()
        if not self.plan_name:
            raise ValidationError({"plan_name": "Package snapshot name is required."})
        if self.status not in {self.STATUS_ACTIVE, self.STATUS_ENDED}:
            raise ValidationError({"status": "Subscription status is not valid."})
        if self.status == self.STATUS_ACTIVE and self.ended_at is not None:
            raise ValidationError({"ended_at": "Active subscriptions cannot have an end time."})
        if self.status == self.STATUS_ENDED and self.ended_at is None:
            raise ValidationError({"ended_at": "Ended subscriptions require an end time."})
        if self.starts_at and timezone.is_naive(self.starts_at):
            raise ValidationError({"starts_at": "Subscription start time must be timezone-aware."})
        if self.ended_at and timezone.is_naive(self.ended_at):
            raise ValidationError({"ended_at": "Subscription end time must be timezone-aware."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Subscription currency must be KES."})
        if self.price_minor is not None and self.price_minor <= 0:
            raise ValidationError({"price_minor": "Subscription price must be greater than zero."})
        if self.download_speed_mbps is not None and self.download_speed_mbps <= 0:
            raise ValidationError(
                {"download_speed_mbps": "Download speed must be greater than zero."}
            )
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValidationError({"duration_days": "Duration must be greater than zero."})
        if self.grace_period_hours is not None and self.grace_period_hours < 0:
            raise ValidationError({"grace_period_hours": "Grace period cannot be negative."})

    def delete(self, *args, **kwargs) -> None:
        msg = "Subscriptions cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_price(self) -> str:
        return format_ksh(self.price_minor)

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    def _reject_protected_changes(self) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        changed = [
            field
            for field in self.IMMUTABLE_FIELDS
            if getattr(current, field) != getattr(self, field)
        ]
        if changed:
            names = ", ".join(sorted(changed))
            raise RuntimeError(f"Subscription fields cannot be changed after creation: {names}.")
        if current.status == self.STATUS_ENDED:
            if self.status != self.STATUS_ENDED:
                raise ValidationError("Ended subscriptions cannot be reactivated.")
            if current.ended_at != self.ended_at:
                raise RuntimeError("Ended subscription end time cannot be changed.")


class BillingPeriodQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "BillingPeriod records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "BillingPeriod records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "BillingPeriod records cannot be deleted through application code."
        raise RuntimeError(msg)


class BillingPeriodManager(models.Manager):
    def get_queryset(self):
        return BillingPeriodQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "BillingPeriod records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class BillingPeriod(models.Model):
    PERIOD_ACTIVATION = "activation"
    PERIOD_RENEWAL = "renewal"
    PERIOD_TYPE_CHOICES = [
        (PERIOD_ACTIVATION, "Activation"),
        (PERIOD_RENEWAL, "Renewal"),
    ]
    IMMUTABLE_FIELDS = (
        "service_id",
        "subscription_id",
        "sequence_number",
        "period_type",
        "operation_id",
        "previous_period_id",
        "effective_at",
        "starts_at",
        "expires_at",
        "grace_until",
        "plan_name",
        "download_speed_mbps",
        "price_minor",
        "currency",
        "duration_days",
        "grace_period_hours",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "subscribers.Service",
        on_delete=models.PROTECT,
        related_name="billing_periods",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="billing_periods",
    )
    sequence_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    period_type = models.CharField(max_length=12, choices=PERIOD_TYPE_CHOICES)
    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    previous_period = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="next_periods",
    )
    effective_at = models.DateTimeField()
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    grace_until = models.DateTimeField()
    plan_name = models.CharField(max_length=120)
    download_speed_mbps = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="KES", editable=False)
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    grace_period_hours = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BillingPeriodManager()

    class Meta:
        verbose_name = "Billing period"
        verbose_name_plural = "Billing periods"
        ordering = ["service", "-sequence_number"]
        indexes = [
            models.Index(
                fields=["service", "sequence_number"],
                name="billing_period_service_seq_idx",
            ),
            models.Index(
                fields=["service", "expires_at"],
                name="billing_period_service_exp_idx",
            ),
            models.Index(fields=["subscription"], name="billing_period_sub_idx"),
            models.Index(fields=["operation_id"], name="billing_period_operation_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "sequence_number"],
                name="billing_period_service_sequence_unique",
            ),
            models.UniqueConstraint(
                fields=["previous_period"],
                condition=Q(previous_period__isnull=False),
                name="billing_period_previous_single_successor",
            ),
            models.CheckConstraint(
                condition=Q(sequence_number__gt=0),
                name="billing_period_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(period_type__in=["activation", "renewal"]),
                name="billing_period_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=F("starts_at")),
                name="billing_period_expires_after_start",
            ),
            models.CheckConstraint(
                condition=Q(grace_until__gte=F("expires_at")),
                name="billing_period_grace_after_expiry",
            ),
            models.CheckConstraint(
                condition=Q(price_minor__gt=0),
                name="billing_period_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(download_speed_mbps__gt=0),
                name="billing_period_download_positive",
            ),
            models.CheckConstraint(
                condition=Q(duration_days__gt=0),
                name="billing_period_duration_positive",
            ),
            models.CheckConstraint(
                condition=Q(grace_period_hours__gte=0),
                name="billing_period_grace_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="billing_period_currency_kes",
            ),
            models.CheckConstraint(
                condition=(
                    Q(period_type="activation", previous_period__isnull=True)
                    | Q(period_type="renewal", previous_period__isnull=False)
                ),
                name="billing_period_previous_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service} billing period {self.sequence_number}"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.plan_name = self.plan_name.strip()
        if not self.plan_name:
            raise ValidationError({"plan_name": "Package snapshot name is required."})
        if self.period_type not in {self.PERIOD_ACTIVATION, self.PERIOD_RENEWAL}:
            raise ValidationError({"period_type": "Billing period type is not valid."})
        if self.period_type == self.PERIOD_ACTIVATION and self.previous_period_id:
            raise ValidationError({"previous_period": "Activation cannot have a previous period."})
        if self.period_type == self.PERIOD_RENEWAL and not self.previous_period_id:
            raise ValidationError({"previous_period": "Renewal requires a previous period."})
        if (
            self.subscription_id
            and self.service_id
            and self.subscription.service_id != self.service_id
        ):
            raise ValidationError({"subscription": "Subscription must belong to this service."})
        if (
            self.previous_period_id
            and self.service_id
            and self.previous_period.service_id != self.service_id
        ):
            raise ValidationError(
                {"previous_period": "Previous period must belong to this service."}
            )
        for field in ["effective_at", "starts_at", "expires_at", "grace_until"]:
            value = getattr(self, field)
            if value and timezone.is_naive(value):
                raise ValidationError({field: "Billing period times must be timezone-aware."})
        if self.expires_at and self.starts_at and self.expires_at <= self.starts_at:
            raise ValidationError({"expires_at": "Billing period expiry must be after start."})
        if self.grace_until and self.expires_at and self.grace_until < self.expires_at:
            raise ValidationError({"grace_until": "Grace time cannot be before expiry."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Billing period currency must be KES."})
        if self.price_minor is not None and self.price_minor <= 0:
            raise ValidationError(
                {"price_minor": "Billing period price must be greater than zero."}
            )
        if self.download_speed_mbps is not None and self.download_speed_mbps <= 0:
            raise ValidationError(
                {"download_speed_mbps": "Download speed must be greater than zero."}
            )
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValidationError({"duration_days": "Duration must be greater than zero."})
        if self.grace_period_hours is not None and self.grace_period_hours < 0:
            raise ValidationError({"grace_period_hours": "Grace period cannot be negative."})

    def delete(self, *args, **kwargs) -> None:
        msg = "BillingPeriod records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_price(self) -> str:
        return format_ksh(self.price_minor)

    def _reject_protected_changes(self) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        changed = [
            field
            for field in self.IMMUTABLE_FIELDS
            if getattr(current, field) != getattr(self, field)
        ]
        if changed:
            names = ", ".join(sorted(changed))
            raise RuntimeError(f"BillingPeriod fields cannot be changed after creation: {names}.")


class WalletQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "Wallet records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "Wallet records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "Wallet records cannot be deleted through application code."
        raise RuntimeError(msg)


class WalletManager(models.Manager):
    def get_queryset(self):
        return WalletQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "Wallet records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class Wallet(models.Model):
    IMMUTABLE_FIELDS = ("subscriber_id", "currency")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.OneToOneField(
        "subscribers.Subscriber",
        on_delete=models.PROTECT,
        related_name="wallet",
    )
    currency = models.CharField(max_length=3, default="KES", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WalletManager()

    class Meta:
        ordering = ["subscriber__account_number"]
        indexes = [models.Index(fields=["subscriber"], name="billing_wallet_subscriber_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(currency="KES"), name="billing_wallet_currency_kes")
        ]

    def __str__(self) -> str:
        return f"{self.subscriber.account_number} wallet"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.currency != "KES":
            raise ValidationError({"currency": "Wallet currency must be KES."})

    def delete(self, *args, **kwargs) -> None:
        msg = "Wallet records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def balance_minor(self) -> int:
        latest_entry = self.entries.order_by("-sequence_number").first()
        if latest_entry is None:
            return 0
        return latest_entry.balance_after_minor

    @property
    def formatted_balance(self) -> str:
        return format_ksh(self.balance_minor)

    def _reject_protected_changes(self) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        changed = [
            field
            for field in self.IMMUTABLE_FIELDS
            if getattr(current, field) != getattr(self, field)
        ]
        if changed:
            names = ", ".join(sorted(changed))
            raise RuntimeError(f"Wallet fields cannot be changed after creation: {names}.")


class LedgerEntryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "LedgerEntry records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "LedgerEntry records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "LedgerEntry records cannot be deleted through application code."
        raise RuntimeError(msg)


class LedgerEntryManager(models.Manager):
    def get_queryset(self):
        return LedgerEntryQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "LedgerEntry records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class LedgerEntry(models.Model):
    ENTRY_MANUAL_CREDIT = "manual_credit"
    ENTRY_MANUAL_DEBIT = "manual_debit"
    ENTRY_REVERSAL = "reversal"
    ENTRY_TYPE_CHOICES = [
        (ENTRY_MANUAL_CREDIT, "Manual credit"),
        (ENTRY_MANUAL_DEBIT, "Manual debit"),
        (ENTRY_REVERSAL, "Reversal"),
    ]
    DIRECTION_CREDIT = "credit"
    DIRECTION_DEBIT = "debit"
    DIRECTION_CHOICES = [
        (DIRECTION_CREDIT, "Credit"),
        (DIRECTION_DEBIT, "Debit"),
    ]
    IMMUTABLE_FIELDS = (
        "wallet_id",
        "sequence_number",
        "operation_id",
        "entry_type",
        "direction",
        "amount_minor",
        "balance_after_minor",
        "currency",
        "previous_entry_id",
        "reverses_entry_id",
        "reason",
        "created_by_id",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    sequence_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    operation_id = models.UUIDField(unique=True, editable=False)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES)
    amount_minor = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY_MINOR)]
    )
    balance_after_minor = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(MAX_MONEY_MINOR)]
    )
    currency = models.CharField(max_length=3, default="KES", editable=False)
    previous_entry = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="next_entries",
    )
    reverses_entry = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal_entry",
    )
    reason = models.CharField(max_length=240)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_ledger_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LedgerEntryManager()

    class Meta:
        verbose_name = "Ledger entry"
        verbose_name_plural = "Ledger entries"
        ordering = ["wallet", "-sequence_number"]
        indexes = [
            models.Index(fields=["wallet", "sequence_number"], name="ledger_entry_wallet_seq_idx"),
            models.Index(fields=["wallet", "created_at"], name="ledger_wallet_created_idx"),
            models.Index(fields=["operation_id"], name="ledger_entry_operation_idx"),
            models.Index(fields=["entry_type"], name="ledger_entry_type_idx"),
            models.Index(fields=["reverses_entry"], name="ledger_entry_reverses_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "sequence_number"],
                name="ledger_entry_wallet_sequence_unique",
            ),
            models.UniqueConstraint(
                fields=["previous_entry"],
                condition=Q(previous_entry__isnull=False),
                name="ledger_entry_previous_single_successor",
            ),
            models.CheckConstraint(
                condition=Q(sequence_number__gt=0),
                name="ledger_entry_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="ledger_entry_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(balance_after_minor__gte=0),
                name="ledger_entry_balance_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="ledger_entry_currency_kes",
            ),
            models.CheckConstraint(
                condition=Q(entry_type__in=["manual_credit", "manual_debit", "reversal"]),
                name="ledger_entry_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(direction__in=["credit", "debit"]),
                name="ledger_entry_direction_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(sequence_number=1, previous_entry__isnull=True)
                    | Q(sequence_number__gt=1, previous_entry__isnull=False)
                ),
                name="ledger_entry_previous_matches_sequence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        entry_type__in=["manual_credit", "manual_debit"],
                        reverses_entry__isnull=True,
                    )
                    | Q(entry_type="reversal", reverses_entry__isnull=False)
                ),
                name="ledger_entry_reversal_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.wallet} ledger entry {self.sequence_number}"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValidationError({"reason": "Reason is required."})
        if self.entry_type not in {
            self.ENTRY_MANUAL_CREDIT,
            self.ENTRY_MANUAL_DEBIT,
            self.ENTRY_REVERSAL,
        }:
            raise ValidationError({"entry_type": "Ledger entry type is not valid."})
        if self.direction not in {self.DIRECTION_CREDIT, self.DIRECTION_DEBIT}:
            raise ValidationError({"direction": "Ledger direction is not valid."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Ledger currency must be KES."})
        if self.sequence_number is not None:
            if self.sequence_number <= 0:
                raise ValidationError({"sequence_number": "Sequence number must be positive."})
            if self.sequence_number == 1 and self.previous_entry_id:
                raise ValidationError(
                    {"previous_entry": "First ledger entry cannot have a previous entry."}
                )
            if self.sequence_number > 1 and not self.previous_entry_id:
                raise ValidationError({"previous_entry": "Ledger entry requires a previous entry."})
        if self.amount_minor is not None and self.amount_minor <= 0:
            raise ValidationError({"amount_minor": "Amount must be greater than zero."})
        if self.amount_minor is not None and self.amount_minor > MAX_MONEY_MINOR:
            raise ValidationError({"amount_minor": "Amount is too large."})
        if self.balance_after_minor is not None and self.balance_after_minor < 0:
            raise ValidationError({"balance_after_minor": "Balance cannot be negative."})
        if self.balance_after_minor is not None and self.balance_after_minor > MAX_MONEY_MINOR:
            raise ValidationError({"balance_after_minor": "Balance is too large."})

        previous_balance = 0
        if self.previous_entry_id:
            if self.wallet_id and self.previous_entry.wallet_id != self.wallet_id:
                raise ValidationError(
                    {"previous_entry": "Previous entry must belong to this wallet."}
                )
            if (
                self.sequence_number is not None
                and self.previous_entry.sequence_number != self.sequence_number - 1
            ):
                raise ValidationError(
                    {"previous_entry": "Previous entry sequence must be exactly one less."}
                )
            previous_balance = self.previous_entry.balance_after_minor
        elif self.sequence_number and self.sequence_number > 1:
            raise ValidationError({"previous_entry": "Ledger entry requires a previous entry."})

        if self.entry_type in {self.ENTRY_MANUAL_CREDIT, self.ENTRY_MANUAL_DEBIT}:
            if self.reverses_entry_id:
                raise ValidationError(
                    {"reverses_entry": "Manual entries cannot reverse another entry."}
                )
        elif self.entry_type == self.ENTRY_REVERSAL:
            self._clean_reversal_target()

        expected_balance = (
            previous_balance + self.amount_minor
            if self.direction == self.DIRECTION_CREDIT
            else previous_balance - self.amount_minor
        )
        if expected_balance < 0:
            raise ValidationError({"balance_after_minor": "Wallet balance cannot become negative."})
        if self.balance_after_minor is not None and self.balance_after_minor != expected_balance:
            raise ValidationError({"balance_after_minor": "Balance after entry is not correct."})

    def delete(self, *args, **kwargs) -> None:
        msg = "LedgerEntry records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_amount(self) -> str:
        return format_ksh(self.amount_minor)

    @property
    def formatted_balance_after(self) -> str:
        return format_ksh(self.balance_after_minor)

    @property
    def is_reversible(self) -> bool:
        if self.entry_type not in {self.ENTRY_MANUAL_CREDIT, self.ENTRY_MANUAL_DEBIT}:
            return False
        return not LedgerEntry.objects.filter(reverses_entry=self).exists()

    def _clean_reversal_target(self) -> None:
        if not self.reverses_entry_id:
            raise ValidationError({"reverses_entry": "Reversal requires a target entry."})
        target = self.reverses_entry
        if self.wallet_id and target.wallet_id != self.wallet_id:
            raise ValidationError({"reverses_entry": "Reversal target must belong to this wallet."})
        if target.entry_type == self.ENTRY_REVERSAL:
            raise ValidationError({"reverses_entry": "A reversal cannot reverse another reversal."})
        if target.entry_type not in {self.ENTRY_MANUAL_CREDIT, self.ENTRY_MANUAL_DEBIT}:
            raise ValidationError({"reverses_entry": "Only manual entries can be reversed."})
        if (
            LedgerEntry.objects.filter(reverses_entry=target)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {"reverses_entry": "This ledger entry has already been reversed."}
            )
        if self.amount_minor != target.amount_minor:
            raise ValidationError(
                {"amount_minor": "Reversal amount must match the original entry."}
            )
        expected_direction = (
            self.DIRECTION_DEBIT
            if target.direction == self.DIRECTION_CREDIT
            else self.DIRECTION_CREDIT
        )
        if self.direction != expected_direction:
            raise ValidationError(
                {"direction": "Reversal direction must oppose the original entry."}
            )

    def _reject_protected_changes(self) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        changed = [
            field
            for field in self.IMMUTABLE_FIELDS
            if getattr(current, field) != getattr(self, field)
        ]
        if changed:
            names = ", ".join(sorted(changed))
            raise RuntimeError(f"LedgerEntry fields cannot be changed after creation: {names}.")
