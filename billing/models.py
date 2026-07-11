from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

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
