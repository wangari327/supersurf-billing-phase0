from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .money import format_ksh


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
