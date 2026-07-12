from __future__ import annotations

import re
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
    IMMUTABLE_FIELDS = ("subscriber_id", "currency", "created_at")
    IMMUTABLE_UPDATE_FIELDS = frozenset(IMMUTABLE_FIELDS) | {"subscriber"}

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
        self._reject_protected_changes(update_fields=kwargs.get("update_fields"))
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

    def _reject_protected_changes(self, update_fields=None) -> None:
        if not self.pk:
            return
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.IMMUTABLE_UPDATE_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(
                    f"Wallet fields cannot be changed after creation: {names}."
                )
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
    ENTRY_BILLING_CHARGE = "billing_charge"
    ENTRY_PAYMENT_CREDIT = "payment_credit"
    ENTRY_REVERSAL = "reversal"
    ENTRY_TYPE_CHOICES = [
        (ENTRY_MANUAL_CREDIT, "Manual credit"),
        (ENTRY_MANUAL_DEBIT, "Manual debit"),
        (ENTRY_BILLING_CHARGE, "Billing charge"),
        (ENTRY_PAYMENT_CREDIT, "Payment credit"),
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
        "created_at",
    )
    IMMUTABLE_UPDATE_FIELDS = frozenset(IMMUTABLE_FIELDS) | {
        "wallet",
        "previous_entry",
        "reverses_entry",
        "created_by",
    }

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
                condition=Q(
                    entry_type__in=[
                        "manual_credit",
                        "manual_debit",
                        "billing_charge",
                        "payment_credit",
                        "reversal",
                    ]
                ),
                name="ledger_entry_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(direction__in=["credit", "debit"]),
                name="ledger_entry_direction_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(entry_type="manual_credit", direction="credit")
                    | Q(entry_type="manual_debit", direction="debit")
                    | Q(entry_type="billing_charge", direction="debit")
                    | Q(entry_type="payment_credit", direction="credit")
                    | Q(entry_type="reversal")
                ),
                name="ledger_entry_type_direction_valid",
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
                        entry_type__in=["manual_credit", "manual_debit", "billing_charge"],
                        reverses_entry__isnull=True,
                    )
                    | Q(entry_type="payment_credit", reverses_entry__isnull=True)
                    | Q(entry_type="reversal", reverses_entry__isnull=False)
                ),
                name="ledger_entry_reversal_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.wallet} ledger entry {self.sequence_number}"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes(update_fields=kwargs.get("update_fields"))
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
            self.ENTRY_BILLING_CHARGE,
            self.ENTRY_PAYMENT_CREDIT,
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

        if self.entry_type == self.ENTRY_MANUAL_CREDIT and self.direction != self.DIRECTION_CREDIT:
            raise ValidationError({"direction": "Manual credits must use credit direction."})
        if self.entry_type == self.ENTRY_MANUAL_DEBIT and self.direction != self.DIRECTION_DEBIT:
            raise ValidationError({"direction": "Manual debits must use debit direction."})
        if (
            self.entry_type == self.ENTRY_BILLING_CHARGE
            and self.direction != self.DIRECTION_DEBIT
        ):
            raise ValidationError({"direction": "Billing charge entries must use debit direction."})
        if (
            self.entry_type == self.ENTRY_PAYMENT_CREDIT
            and self.direction != self.DIRECTION_CREDIT
        ):
            raise ValidationError(
                {"direction": "Payment credit entries must use credit direction."}
            )

        if self.entry_type in {
            self.ENTRY_MANUAL_CREDIT,
            self.ENTRY_MANUAL_DEBIT,
            self.ENTRY_BILLING_CHARGE,
            self.ENTRY_PAYMENT_CREDIT,
        }:
            if self.reverses_entry_id:
                raise ValidationError(
                    {"reverses_entry": "This ledger entry type cannot reverse another entry."}
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

    def _reject_protected_changes(self, update_fields=None) -> None:
        if not self.pk:
            return
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.IMMUTABLE_UPDATE_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(
                    f"LedgerEntry fields cannot be changed after creation: {names}."
                )
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


class BillingChargeQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "BillingCharge records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "BillingCharge records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "BillingCharge records cannot be deleted through application code."
        raise RuntimeError(msg)


class BillingChargeManager(models.Manager):
    def get_queryset(self):
        return BillingChargeQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "BillingCharge records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class BillingCharge(models.Model):
    CHARGE_ACTIVATION = "activation"
    CHARGE_RENEWAL = "renewal"
    CHARGE_TYPE_CHOICES = [
        (CHARGE_ACTIVATION, "Activation"),
        (CHARGE_RENEWAL, "Renewal"),
    ]
    IMMUTABLE_FIELDS = (
        "service_id",
        "subscription_id",
        "billing_period_id",
        "wallet_id",
        "ledger_entry_id",
        "operation_id",
        "charge_type",
        "amount_minor",
        "currency",
        "reason",
        "created_by_id",
        "created_at",
    )
    IMMUTABLE_UPDATE_FIELDS = frozenset(IMMUTABLE_FIELDS) | {
        "service",
        "subscription",
        "billing_period",
        "wallet",
        "ledger_entry",
        "created_by",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "subscribers.Service",
        on_delete=models.PROTECT,
        related_name="billing_charges",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="billing_charges",
    )
    billing_period = models.OneToOneField(
        BillingPeriod,
        on_delete=models.PROTECT,
        related_name="billing_charge",
    )
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="billing_charges")
    ledger_entry = models.OneToOneField(
        LedgerEntry,
        on_delete=models.PROTECT,
        related_name="billing_charge",
    )
    operation_id = models.UUIDField(unique=True, editable=False)
    charge_type = models.CharField(max_length=12, choices=CHARGE_TYPE_CHOICES)
    amount_minor = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY_MINOR)]
    )
    currency = models.CharField(max_length=3, default="KES", editable=False)
    reason = models.CharField(max_length=240)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_billing_charges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BillingChargeManager()

    class Meta:
        verbose_name = "Billing charge"
        verbose_name_plural = "Billing charges"
        ordering = ["service", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["service", "charge_type"], name="bill_charge_service_type_idx"),
            models.Index(fields=["wallet", "created_at"], name="bill_charge_wallet_created_idx"),
            models.Index(fields=["operation_id"], name="billing_charge_operation_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="billing_charge_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="billing_charge_currency_kes",
            ),
            models.CheckConstraint(
                condition=Q(charge_type__in=["activation", "renewal"]),
                name="billing_charge_type_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service} {self.charge_type} charge"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValidationError({"reason": "Reason is required."})
        if self.charge_type not in {self.CHARGE_ACTIVATION, self.CHARGE_RENEWAL}:
            raise ValidationError({"charge_type": "Billing charge type is not valid."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Billing charge currency must be KES."})
        if self.amount_minor is not None and self.amount_minor <= 0:
            raise ValidationError({"amount_minor": "Charge amount must be greater than zero."})
        if self.amount_minor is not None and self.amount_minor > MAX_MONEY_MINOR:
            raise ValidationError({"amount_minor": "Charge amount is too large."})

        if (
            self.service_id
            and self.subscription_id
            and self.subscription.service_id != self.service_id
        ):
            raise ValidationError({"subscription": "Subscription must belong to this service."})
        if (
            self.service_id
            and self.billing_period_id
            and self.billing_period.service_id != self.service_id
        ):
            raise ValidationError({"billing_period": "Billing period must belong to this service."})
        if (
            self.subscription_id
            and self.billing_period_id
            and self.billing_period.subscription_id != self.subscription_id
        ):
            raise ValidationError(
                {"billing_period": "Billing period must use this subscription."}
            )
        if (
            self.service_id
            and self.wallet_id
            and self.wallet.subscriber_id != self.service.subscriber_id
        ):
            raise ValidationError({"wallet": "Wallet must belong to this service subscriber."})
        if (
            self.wallet_id
            and self.ledger_entry_id
            and self.ledger_entry.wallet_id != self.wallet_id
        ):
            raise ValidationError({"ledger_entry": "Ledger entry must belong to this wallet."})
        if self.ledger_entry_id:
            if self.ledger_entry.entry_type != LedgerEntry.ENTRY_BILLING_CHARGE:
                raise ValidationError({"ledger_entry": "Ledger entry must be a billing charge."})
            if self.ledger_entry.direction != LedgerEntry.DIRECTION_DEBIT:
                raise ValidationError({"ledger_entry": "Billing charge ledger entry must debit."})
            if (
                self.amount_minor is not None
                and self.ledger_entry.amount_minor != self.amount_minor
            ):
                raise ValidationError(
                    {"amount_minor": "Ledger entry amount must match the charge amount."}
                )
            if self.ledger_entry.currency != self.currency:
                raise ValidationError(
                    {"currency": "Ledger entry currency must match the charge currency."}
                )
            if self.ledger_entry.operation_id != self.operation_id:
                raise ValidationError(
                    {"operation_id": "Ledger entry operation ID must match the charge."}
                )
            if self.created_by_id and self.ledger_entry.created_by_id != self.created_by_id:
                raise ValidationError(
                    {"created_by": "Ledger entry operator must match the charge operator."}
                )
        if self.billing_period_id:
            if (
                self.amount_minor is not None
                and self.billing_period.price_minor != self.amount_minor
            ):
                raise ValidationError(
                    {"amount_minor": "Billing period price must match the charge amount."}
                )
            if self.billing_period.operation_id != self.operation_id:
                raise ValidationError(
                    {"operation_id": "Billing period operation ID must match the charge."}
                )
            if (
                self.charge_type == self.CHARGE_ACTIVATION
                and self.billing_period.period_type != BillingPeriod.PERIOD_ACTIVATION
            ):
                raise ValidationError(
                    {"charge_type": "Activation charge requires an activation period."}
                )
            if (
                self.charge_type == self.CHARGE_RENEWAL
                and self.billing_period.period_type != BillingPeriod.PERIOD_RENEWAL
            ):
                raise ValidationError(
                    {"charge_type": "Renewal charge requires a renewal period."}
                )

    def delete(self, *args, **kwargs) -> None:
        msg = "BillingCharge records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_amount(self) -> str:
        return format_ksh(self.amount_minor)

    def _reject_protected_changes(self, update_fields=None) -> None:
        if not self.pk:
            return
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.IMMUTABLE_UPDATE_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(
                    f"BillingCharge fields cannot be changed after creation: {names}."
                )
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
            raise RuntimeError(
                f"BillingCharge fields cannot be changed after creation: {names}."
            )


class PaymentProviderProfile(models.Model):
    PROVIDER_FAKE = "fake"
    PROVIDER_MPESA = "mpesa"
    PROVIDER_CHOICES = [
        (PROVIDER_FAKE, "Fake"),
        (PROVIDER_MPESA, "M-PESA"),
    ]
    PRODUCT_FAKE = "fake"
    PRODUCT_PAYBILL = "paybill"
    PRODUCT_TILL = "till"
    PRODUCT_CHOICES = [
        (PRODUCT_FAKE, "Fake"),
        (PRODUCT_PAYBILL, "Paybill"),
        (PRODUCT_TILL, "Till"),
    ]
    ENVIRONMENT_TEST = "test"
    ENVIRONMENT_SANDBOX = "sandbox"
    ENVIRONMENT_PRODUCTION = "production"
    ENVIRONMENT_CHOICES = [
        (ENVIRONMENT_TEST, "Test"),
        (ENVIRONMENT_SANDBOX, "Sandbox"),
        (ENVIRONMENT_PRODUCTION, "Production"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=12, choices=PROVIDER_CHOICES)
    product_type = models.CharField(max_length=12, choices=PRODUCT_CHOICES)
    environment = models.CharField(max_length=12, choices=ENVIRONMENT_CHOICES)
    external_identifier = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment provider profile"
        verbose_name_plural = "Payment provider profiles"
        ordering = ["provider", "product_type", "environment", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "product_type", "environment", "external_identifier"],
                name="payment_provider_profile_unique",
            ),
            models.CheckConstraint(
                condition=Q(provider__in=["fake", "mpesa"]),
                name="payment_provider_valid",
            ),
            models.CheckConstraint(
                condition=Q(product_type__in=["fake", "paybill", "till"]),
                name="payment_provider_product_valid",
            ),
            models.CheckConstraint(
                condition=Q(environment__in=["test", "sandbox", "production"]),
                name="payment_provider_environment_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        self.external_identifier = self.external_identifier.strip()
        if not self.name:
            raise ValidationError({"name": "Payment provider profile name is required."})
        if not self.external_identifier:
            raise ValidationError({"external_identifier": "External identifier is required."})
        if self.provider not in {self.PROVIDER_FAKE, self.PROVIDER_MPESA}:
            raise ValidationError({"provider": "Payment provider is not valid."})
        if self.product_type not in {
            self.PRODUCT_FAKE,
            self.PRODUCT_PAYBILL,
            self.PRODUCT_TILL,
        }:
            raise ValidationError({"product_type": "Payment product type is not valid."})
        if self.environment not in {
            self.ENVIRONMENT_TEST,
            self.ENVIRONMENT_SANDBOX,
            self.ENVIRONMENT_PRODUCTION,
        }:
            raise ValidationError({"environment": "Payment environment is not valid."})


class PaymentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "Payment records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "Payment records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "Payment records cannot be deleted through application code."
        raise RuntimeError(msg)


class PaymentManager(models.Manager):
    def get_queryset(self):
        return PaymentQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "Payment records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class Payment(models.Model):
    IMMUTABLE_FIELDS = (
        "provider_profile_id",
        "provider_transaction_id",
        "amount_minor",
        "currency",
        "received_at",
        "account_reference",
        "payload_digest",
        "created_at",
    )
    IMMUTABLE_UPDATE_FIELDS = frozenset(IMMUTABLE_FIELDS) | {"provider_profile"}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_profile = models.ForeignKey(
        PaymentProviderProfile,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    provider_transaction_id = models.CharField(max_length=128)
    amount_minor = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY_MINOR)]
    )
    currency = models.CharField(max_length=3, default="KES", editable=False)
    received_at = models.DateTimeField()
    account_reference = models.CharField(max_length=64, blank=True)
    payload_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PaymentManager()

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-received_at", "-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["provider_profile", "provider_transaction_id"],
                name="payment_provider_tx_idx",
            ),
            models.Index(fields=["account_reference"], name="payment_account_ref_idx"),
            models.Index(fields=["received_at"], name="payment_received_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_profile", "provider_transaction_id"],
                name="payment_provider_transaction_unique",
            ),
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=~Q(provider_transaction_id=""),
                name="payment_provider_transaction_nonblank",
            ),
            models.CheckConstraint(condition=Q(currency="KES"), name="payment_currency_kes"),
        ]

    def __str__(self) -> str:
        return self.provider_transaction_id

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.provider_transaction_id = self.provider_transaction_id.strip()
        self.account_reference = self.account_reference.strip().upper()
        self.payload_digest = self.payload_digest.strip().lower()
        if not self.provider_transaction_id:
            raise ValidationError(
                {"provider_transaction_id": "Provider transaction ID is required."}
            )
        if self.amount_minor is not None and self.amount_minor <= 0:
            raise ValidationError({"amount_minor": "Payment amount must be greater than zero."})
        if self.amount_minor is not None and self.amount_minor > MAX_MONEY_MINOR:
            raise ValidationError({"amount_minor": "Payment amount is too large."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Payment currency must be KES."})
        if self.received_at and timezone.is_naive(self.received_at):
            raise ValidationError({"received_at": "Payment received time must be timezone-aware."})
        if self.payload_digest and not re.fullmatch(r"[0-9a-f]{64}", self.payload_digest):
            raise ValidationError({"payload_digest": "Payload digest must be a SHA-256 digest."})

    def delete(self, *args, **kwargs) -> None:
        msg = "Payment records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_amount(self) -> str:
        return format_ksh(self.amount_minor)

    @property
    def allocated_amount_minor(self) -> int:
        return sum(allocation.amount_minor for allocation in self.allocations.all())

    @property
    def is_allocated(self) -> bool:
        return self.allocated_amount_minor == self.amount_minor

    @property
    def derived_state(self) -> str:
        if self.is_allocated:
            return "allocated"
        return "unmatched"

    def _reject_protected_changes(self, update_fields=None) -> None:
        if not self.pk:
            return
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.IMMUTABLE_UPDATE_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(f"Payment fields cannot be changed after creation: {names}.")
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
            raise RuntimeError(f"Payment fields cannot be changed after creation: {names}.")


class PaymentAllocationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "PaymentAllocation records cannot be updated through application code."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "PaymentAllocation records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "PaymentAllocation records cannot be deleted through application code."
        raise RuntimeError(msg)


class PaymentAllocationManager(models.Manager):
    def get_queryset(self):
        return PaymentAllocationQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "PaymentAllocation records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class PaymentAllocation(models.Model):
    ALLOCATION_WALLET_CREDIT = "wallet_credit"
    ALLOCATION_TYPE_CHOICES = [(ALLOCATION_WALLET_CREDIT, "Wallet credit")]
    IMMUTABLE_FIELDS = (
        "payment_id",
        "wallet_id",
        "ledger_entry_id",
        "operation_id",
        "allocation_type",
        "amount_minor",
        "currency",
        "created_by_id",
        "created_at",
    )
    IMMUTABLE_UPDATE_FIELDS = frozenset(IMMUTABLE_FIELDS) | {
        "payment",
        "wallet",
        "ledger_entry",
        "created_by",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    ledger_entry = models.OneToOneField(
        LedgerEntry,
        on_delete=models.PROTECT,
        related_name="payment_allocation",
    )
    operation_id = models.UUIDField(unique=True, editable=False)
    allocation_type = models.CharField(
        max_length=20,
        choices=ALLOCATION_TYPE_CHOICES,
        default=ALLOCATION_WALLET_CREDIT,
        editable=False,
    )
    amount_minor = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY_MINOR)]
    )
    currency = models.CharField(max_length=3, default="KES", editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payment_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PaymentAllocationManager()

    class Meta:
        verbose_name = "Payment allocation"
        verbose_name_plural = "Payment allocations"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["payment"], name="payment_allocation_payment_idx"),
            models.Index(fields=["wallet", "created_at"], name="pay_alloc_wallet_created_idx"),
            models.Index(fields=["operation_id"], name="payment_alloc_operation_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["payment"], name="one_allocation_per_payment"),
            models.CheckConstraint(
                condition=Q(allocation_type="wallet_credit"),
                name="payment_allocation_type_wallet",
            ),
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="payment_allocation_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(currency="KES"),
                name="payment_allocation_currency_kes",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.payment} allocation"

    def save(self, *args, **kwargs) -> None:
        self._reject_protected_changes(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.allocation_type != self.ALLOCATION_WALLET_CREDIT:
            raise ValidationError({"allocation_type": "Allocation type must be wallet credit."})
        if self.currency != "KES":
            raise ValidationError({"currency": "Payment allocation currency must be KES."})
        if self.amount_minor is not None and self.amount_minor <= 0:
            raise ValidationError({"amount_minor": "Allocation amount must be greater than zero."})
        if self.amount_minor is not None and self.amount_minor > MAX_MONEY_MINOR:
            raise ValidationError({"amount_minor": "Allocation amount is too large."})
        if self.payment_id:
            if self.amount_minor is not None and self.payment.amount_minor != self.amount_minor:
                raise ValidationError(
                    {"amount_minor": "Phase 8 allocations must equal the full payment amount."}
                )
            if self.payment.currency != self.currency:
                raise ValidationError(
                    {"currency": "Allocation currency must match payment currency."}
                )
            if self.pk is None and self.payment.allocations.exists():
                raise ValidationError({"payment": "Payment already has an allocation."})
        if (
            self.wallet_id
            and self.ledger_entry_id
            and self.ledger_entry.wallet_id != self.wallet_id
        ):
            raise ValidationError({"ledger_entry": "Ledger entry must belong to this wallet."})
        if self.ledger_entry_id:
            if self.ledger_entry.entry_type != LedgerEntry.ENTRY_PAYMENT_CREDIT:
                raise ValidationError({"ledger_entry": "Ledger entry must be a payment credit."})
            if self.ledger_entry.direction != LedgerEntry.DIRECTION_CREDIT:
                raise ValidationError({"ledger_entry": "Payment credit ledger entry must credit."})
            if self.ledger_entry.amount_minor != self.amount_minor:
                raise ValidationError(
                    {"amount_minor": "Ledger entry amount must match allocation amount."}
                )
            if self.ledger_entry.currency != self.currency:
                raise ValidationError(
                    {"currency": "Ledger entry currency must match allocation currency."}
                )
            if self.ledger_entry.operation_id != self.operation_id:
                raise ValidationError(
                    {"operation_id": "Ledger entry operation ID must match allocation."}
                )
            if self.created_by_id and self.ledger_entry.created_by_id != self.created_by_id:
                raise ValidationError(
                    {"created_by": "Ledger entry operator must match allocation operator."}
                )

    def delete(self, *args, **kwargs) -> None:
        msg = "PaymentAllocation records cannot be deleted through application code."
        raise RuntimeError(msg)

    @property
    def formatted_amount(self) -> str:
        return format_ksh(self.amount_minor)

    def _reject_protected_changes(self, update_fields=None) -> None:
        if not self.pk:
            return
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.IMMUTABLE_UPDATE_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(
                    f"PaymentAllocation fields cannot be changed after creation: {names}."
                )
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
            raise RuntimeError(
                f"PaymentAllocation fields cannot be changed after creation: {names}."
            )


class UnmatchedPaymentCaseQuerySet(models.QuerySet):
    def update(self, **kwargs):
        msg = "UnmatchedPaymentCase records cannot be updated through bulk paths."
        raise RuntimeError(msg)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "UnmatchedPaymentCase records cannot be bulk-updated through application code."
        raise RuntimeError(msg)

    def delete(self):
        msg = "UnmatchedPaymentCase records cannot be deleted through application code."
        raise RuntimeError(msg)


class UnmatchedPaymentCaseManager(models.Manager):
    def get_queryset(self):
        return UnmatchedPaymentCaseQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        msg = "UnmatchedPaymentCase records cannot be bulk-updated through application code."
        raise RuntimeError(msg)


class UnmatchedPaymentCase(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    ]
    REASON_MISSING_REFERENCE = "missing_reference"
    REASON_INVALID_REFERENCE = "invalid_reference"
    REASON_SUBSCRIBER_NOT_FOUND = "subscriber_not_found"
    REASON_CODE_CHOICES = [
        (REASON_MISSING_REFERENCE, "Missing reference"),
        (REASON_INVALID_REFERENCE, "Invalid reference"),
        (REASON_SUBSCRIBER_NOT_FOUND, "Subscriber not found"),
    ]
    PROTECTED_FIELDS = ("payment_id", "reason_code", "opened_at")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="unmatched_case",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reason_code = models.CharField(max_length=32, choices=REASON_CODE_CHOICES)
    resolved_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_unmatched_payment_cases",
    )
    resolution_allocation = models.OneToOneField(
        PaymentAllocation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_unmatched_case",
    )
    resolution_reason = models.CharField(max_length=240, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_unmatched_payment_cases",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    objects = UnmatchedPaymentCaseManager()

    class Meta:
        verbose_name = "Unmatched payment case"
        verbose_name_plural = "Unmatched payment cases"
        ordering = ["status", "-opened_at", "-id"]
        indexes = [
            models.Index(fields=["status", "opened_at"], name="unmatched_status_opened_idx"),
            models.Index(fields=["reason_code"], name="unmatched_case_reason_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["open", "resolved"]),
                name="unmatched_case_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    reason_code__in=[
                        "missing_reference",
                        "invalid_reference",
                        "subscriber_not_found",
                    ]
                ),
                name="unmatched_case_reason_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.payment} unmatched case"

    def save(self, *args, **kwargs) -> None:
        self._reject_unapproved_resolution(update_fields=kwargs.get("update_fields"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.resolution_reason = self.resolution_reason.strip()
        if self.status not in {self.STATUS_OPEN, self.STATUS_RESOLVED}:
            raise ValidationError({"status": "Unmatched case status is not valid."})
        if self.reason_code not in {
            self.REASON_MISSING_REFERENCE,
            self.REASON_INVALID_REFERENCE,
            self.REASON_SUBSCRIBER_NOT_FOUND,
        }:
            raise ValidationError({"reason_code": "Unmatched reason code is not valid."})
        resolution_fields = [
            self.resolved_wallet_id,
            self.resolution_allocation_id,
            self.resolution_reason,
            self.resolved_by_id,
            self.resolved_at,
        ]
        if self.status == self.STATUS_OPEN and any(resolution_fields):
            raise ValidationError("Open unmatched cases cannot have resolution fields.")
        if self.status == self.STATUS_RESOLVED:
            if not all(resolution_fields):
                raise ValidationError("Resolved unmatched cases require resolution fields.")
            if timezone.is_naive(self.resolved_at):
                raise ValidationError({"resolved_at": "Resolution time must be timezone-aware."})
        if self.resolution_allocation_id:
            if self.resolution_allocation.payment_id != self.payment_id:
                raise ValidationError(
                    {"resolution_allocation": "Resolution allocation must use this payment."}
                )
            if (
                self.resolved_wallet_id
                and self.resolution_allocation.wallet_id != self.resolved_wallet_id
            ):
                raise ValidationError(
                    {"resolution_allocation": "Resolution allocation must use this wallet."}
                )

    def delete(self, *args, **kwargs) -> None:
        msg = "UnmatchedPaymentCase records cannot be deleted through application code."
        raise RuntimeError(msg)

    def _reject_unapproved_resolution(self, update_fields=None) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        changed = [
            field
            for field in (
                "status",
                "resolved_wallet_id",
                "resolution_allocation_id",
                "resolution_reason",
                "resolved_by_id",
                "resolved_at",
                *self.PROTECTED_FIELDS,
            )
            if getattr(current, field) != getattr(self, field)
        ]
        if not changed:
            return
        if current.status == self.STATUS_RESOLVED:
            raise RuntimeError("Resolved unmatched payment cases cannot be changed.")
        if not getattr(self, "_allow_resolution_save", False):
            names = ", ".join(sorted(changed))
            raise RuntimeError(
                "UnmatchedPaymentCase changes require the resolution service: "
                f"{names}."
            )
        if update_fields is not None:
            protected = {str(field) for field in update_fields}.intersection(
                self.PROTECTED_FIELDS
            )
            if protected:
                names = ", ".join(sorted(protected))
                raise RuntimeError(
                    f"UnmatchedPaymentCase fields cannot be changed: {names}."
                )
