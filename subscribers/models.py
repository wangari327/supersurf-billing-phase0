from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from .phone import normalize_kenyan_phone


class ImmutableFieldQuerySet(models.QuerySet):
    immutable_update_fields: frozenset[str] = frozenset()

    def _reject_immutable_updates(self, fields) -> None:
        requested = {str(field) for field in fields}
        immutable = requested.intersection(self.immutable_update_fields)
        if immutable:
            names = ", ".join(sorted(immutable))
            msg = f"Immutable field updates are not allowed: {names}."
            raise RuntimeError(msg)

    def update(self, **kwargs):
        self._reject_immutable_updates(kwargs.keys())
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        self._reject_immutable_updates(fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)


class SubscriberQuerySet(ImmutableFieldQuerySet):
    immutable_update_fields = frozenset({"account_number"})


class ServiceQuerySet(ImmutableFieldQuerySet):
    immutable_update_fields = frozenset(
        {"subscriber", "subscriber_id", "service_number", "service_reference"}
    )


class SubscriberManager(models.Manager):
    def get_queryset(self):
        return SubscriberQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        self.get_queryset()._reject_immutable_updates(fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)


class ServiceManager(models.Manager):
    def get_queryset(self):
        return ServiceQuerySet(self.model, using=self._db)

    def bulk_update(self, objs, fields, batch_size=None):
        self.get_queryset()._reject_immutable_updates(fields)
        return super().bulk_update(objs, fields, batch_size=batch_size)


class SubscriberSequence(models.Model):
    key = models.CharField(max_length=80, unique=True)
    next_value = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ["key"]
        verbose_name = "Subscriber allocation sequence"
        verbose_name_plural = "Subscriber allocation sequences"

    def __str__(self) -> str:
        return self.key


class Subscriber(models.Model):
    CUSTOMER_INDIVIDUAL = "individual"
    CUSTOMER_BUSINESS = "business"
    CUSTOMER_TYPE_CHOICES = [
        (CUSTOMER_INDIVIDUAL, "Individual"),
        (CUSTOMER_BUSINESS, "Business"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_number = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        validators=[
            RegexValidator(
                regex=r"^SS\d{6}$",
                message="Subscriber account number must use the SS000001 format.",
            )
        ],
    )
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES)
    display_name = models.CharField(max_length=160)
    primary_phone = models.CharField(max_length=16)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriberManager()

    class Meta:
        ordering = ["account_number"]

    def __str__(self) -> str:
        return f"{self.account_number} {self.display_name}"

    def save(self, *args, **kwargs) -> None:
        self._reject_identifier_change()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.display_name = self.display_name.strip()
        self.email = self.email.strip()
        if not self.display_name:
            raise ValidationError({"display_name": "Display name is required."})
        self.primary_phone = normalize_kenyan_phone(self.primary_phone)

    def _reject_identifier_change(self) -> None:
        if not self.pk:
            return
        try:
            current = type(self).objects.only("account_number").get(pk=self.pk)
        except type(self).DoesNotExist:
            return
        if current.account_number != self.account_number:
            msg = "Subscriber account number cannot be changed."
            raise RuntimeError(msg)


class Service(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.PROTECT,
        related_name="services",
    )
    service_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    service_reference = models.CharField(
        max_length=11,
        unique=True,
        editable=False,
        validators=[
            RegexValidator(
                regex=r"^SS\d{6}-\d{2}$",
                message="Service reference must use the SS000001-01 format.",
            )
        ],
    )
    label = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceManager()

    class Meta:
        ordering = ["subscriber__account_number", "service_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber", "service_number"],
                name="subscribers_service_number_per_subscriber_unique",
            ),
            models.CheckConstraint(
                condition=Q(service_number__gte=1) & Q(service_number__lte=99),
                name="subscribers_service_number_1_99",
            ),
        ]

    def __str__(self) -> str:
        return self.service_reference

    def save(self, *args, **kwargs) -> None:
        self._reject_identifier_change()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.label = self.label.strip()
        if not self.label:
            raise ValidationError({"label": "Service label is required."})
        if self.service_number is not None and not 1 <= self.service_number <= 99:
            raise ValidationError({"service_number": "Service number must be between 1 and 99."})
        if self.subscriber_id and self.service_number and self.service_reference:
            expected_reference = f"{self.subscriber.account_number}-{self.service_number:02d}"
            if self.service_reference != expected_reference:
                raise ValidationError(
                    {"service_reference": "Service reference does not match the subscriber."}
                )

    def _reject_identifier_change(self) -> None:
        if not self.pk:
            return
        try:
            current = (
                type(self)
                .objects.only("subscriber_id", "service_number", "service_reference")
                .get(pk=self.pk)
            )
        except type(self).DoesNotExist:
            return
        if current.subscriber_id != self.subscriber_id:
            raise RuntimeError("Service subscriber cannot be changed.")
        if current.service_number != self.service_number:
            raise RuntimeError("Service number cannot be changed.")
        if current.service_reference != self.service_reference:
            raise RuntimeError("Service reference cannot be changed.")
