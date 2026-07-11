from __future__ import annotations

from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest

from audit.service import record_event

from .models import Service, Subscriber, SubscriberSequence

ACCOUNT_SEQUENCE_KEY = "subscriber_account"
SUBSCRIBER_PROFILE_FIELDS = [
    "customer_type",
    "display_name",
    "primary_phone",
    "email",
]
SERVICE_PROFILE_FIELDS = ["label"]


def _lock_sequence(key: str) -> SubscriberSequence:
    try:
        return SubscriberSequence.objects.select_for_update().get(key=key)
    except SubscriberSequence.DoesNotExist:
        try:
            sequence = SubscriberSequence.objects.create(key=key, next_value=1)
        except IntegrityError:
            return SubscriberSequence.objects.select_for_update().get(key=key)
        return SubscriberSequence.objects.select_for_update().get(pk=sequence.pk)


def _service_sequence_key(subscriber: Subscriber) -> str:
    return f"subscriber:{subscriber.pk}:service"


def _changed_fields(old: dict[str, object], fields: Sequence[str], cleaned_data) -> list[str]:
    return [field for field in fields if old.get(field) != cleaned_data[field]]


def _status_label(is_active: bool) -> str:
    return "active" if is_active else "inactive"


def allocate_account_number() -> str:
    sequence = _lock_sequence(ACCOUNT_SEQUENCE_KEY)
    next_value = sequence.next_value
    while True:
        account_number = f"SS{next_value:06d}"
        if not Subscriber.objects.filter(account_number=account_number).exists():
            sequence.next_value = next_value + 1
            sequence.save(update_fields=["next_value", "updated_at"])
            return account_number
        next_value += 1


def allocate_service_identity(subscriber: Subscriber) -> tuple[int, str]:
    sequence = _lock_sequence(_service_sequence_key(subscriber))
    next_value = sequence.next_value
    while next_value <= 99:
        service_reference = f"{subscriber.account_number}-{next_value:02d}"
        if not Service.objects.filter(service_reference=service_reference).exists():
            sequence.next_value = next_value + 1
            sequence.save(update_fields=["next_value", "updated_at"])
            return next_value, service_reference
        next_value += 1
    raise ValidationError("A subscriber can have at most 99 services.")


@transaction.atomic
def create_subscriber(*, form, actor, request: HttpRequest | None = None) -> Subscriber:
    account_number = allocate_account_number()
    subscriber = Subscriber(
        account_number=account_number,
        customer_type=form.cleaned_data["customer_type"],
        display_name=form.cleaned_data["display_name"],
        primary_phone=form.cleaned_data["primary_phone"],
        email=form.cleaned_data["email"],
    )
    subscriber.save()
    record_event(
        action="subscriber.created",
        actor=actor,
        request=request,
        target_type="subscriber",
        target_identifier=subscriber.account_number,
        metadata={
            "generated_account_number": subscriber.account_number,
            "changed_fields": [*SUBSCRIBER_PROFILE_FIELDS, "is_active"],
        },
        reason=form.cleaned_data["reason"],
    )
    return subscriber


@transaction.atomic
def update_subscriber(*, subscriber: Subscriber, form, actor, request: HttpRequest | None = None):
    locked_subscriber = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    old = {field: getattr(locked_subscriber, field) for field in SUBSCRIBER_PROFILE_FIELDS}
    for field in SUBSCRIBER_PROFILE_FIELDS:
        setattr(locked_subscriber, field, form.cleaned_data[field])
    locked_subscriber.save()
    record_event(
        action="subscriber.updated",
        actor=actor,
        request=request,
        target_type="subscriber",
        target_identifier=locked_subscriber.account_number,
        metadata={
            "changed_fields": _changed_fields(old, SUBSCRIBER_PROFILE_FIELDS, form.cleaned_data)
        },
        reason=form.cleaned_data["reason"],
    )
    return locked_subscriber


@transaction.atomic
def set_subscriber_active(
    *,
    subscriber: Subscriber,
    is_active: bool,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Subscriber:
    locked_subscriber = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    if locked_subscriber.is_active == is_active:
        state = _status_label(is_active)
        raise ValidationError(f"Subscriber {locked_subscriber.account_number} is already {state}.")
    old_status = _status_label(locked_subscriber.is_active)
    locked_subscriber.is_active = is_active
    locked_subscriber.save(update_fields=["is_active", "updated_at"])
    new_status = _status_label(locked_subscriber.is_active)
    record_event(
        action="subscriber.reactivated" if is_active else "subscriber.deactivated",
        actor=actor,
        request=request,
        target_type="subscriber",
        target_identifier=locked_subscriber.account_number,
        metadata={"status_transition": {"from": old_status, "to": new_status}},
        reason=reason,
    )
    return locked_subscriber


@transaction.atomic
def create_service(*, subscriber: Subscriber, form, actor, request: HttpRequest | None = None):
    locked_subscriber = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    service_number, service_reference = allocate_service_identity(locked_subscriber)
    service = Service(
        subscriber=locked_subscriber,
        service_number=service_number,
        service_reference=service_reference,
        label=form.cleaned_data["label"],
    )
    service.save()
    record_event(
        action="service.created",
        actor=actor,
        request=request,
        target_type="service",
        target_identifier=service.service_reference,
        metadata={
            "generated_service_reference": service.service_reference,
            "service_number": service.service_number,
            "changed_fields": [*SERVICE_PROFILE_FIELDS, "is_active"],
        },
        reason=form.cleaned_data["reason"],
    )
    return service


@transaction.atomic
def update_service(*, service: Service, form, actor, request: HttpRequest | None = None):
    locked_service = (
        Service.objects.select_for_update().select_related("subscriber").get(pk=service.pk)
    )
    old = {field: getattr(locked_service, field) for field in SERVICE_PROFILE_FIELDS}
    for field in SERVICE_PROFILE_FIELDS:
        setattr(locked_service, field, form.cleaned_data[field])
    locked_service.save()
    record_event(
        action="service.updated",
        actor=actor,
        request=request,
        target_type="service",
        target_identifier=locked_service.service_reference,
        metadata={
            "changed_fields": _changed_fields(old, SERVICE_PROFILE_FIELDS, form.cleaned_data)
        },
        reason=form.cleaned_data["reason"],
    )
    return locked_service


@transaction.atomic
def set_service_active(
    *,
    service: Service,
    is_active: bool,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Service:
    locked_service = (
        Service.objects.select_for_update().select_related("subscriber").get(pk=service.pk)
    )
    if locked_service.is_active == is_active:
        state = _status_label(is_active)
        raise ValidationError(f"Service {locked_service.service_reference} is already {state}.")
    old_status = _status_label(locked_service.is_active)
    locked_service.is_active = is_active
    locked_service.save(update_fields=["is_active", "updated_at"])
    new_status = _status_label(locked_service.is_active)
    record_event(
        action="service.reactivated" if is_active else "service.deactivated",
        actor=actor,
        request=request,
        target_type="service",
        target_identifier=locked_service.service_reference,
        metadata={"status_transition": {"from": old_status, "to": new_status}},
        reason=reason,
    )
    return locked_service
