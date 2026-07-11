from __future__ import annotations

from collections.abc import Mapping

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from audit.service import record_event
from subscribers.models import Service

from .models import Plan, Subscription

AUDITED_FIELDS = [
    "name",
    "download_speed_mbps",
    "price_minor",
    "currency",
    "duration_days",
    "grace_period_hours",
    "description",
    "is_active",
]
SUBSCRIPTION_SNAPSHOT_FIELDS = [
    "plan_name",
    "download_speed_mbps",
    "price_minor",
    "currency",
    "duration_days",
    "grace_period_hours",
]


def snapshot(plan: Plan) -> dict[str, object]:
    return {field: getattr(plan, field) for field in AUDITED_FIELDS}


def changed_metadata(old: Mapping[str, object], plan: Plan) -> dict[str, object]:
    new = snapshot(plan)
    changed_fields = [field for field in AUDITED_FIELDS if old.get(field) != new[field]]
    return {
        "changed_fields": changed_fields,
        "old": {field: old[field] for field in changed_fields},
        "new": {field: new[field] for field in changed_fields},
    }


def _require_permission(actor, *permissions: str) -> None:
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Subscription changes require an authenticated operator.")
    missing = [permission for permission in permissions if not actor.has_perm(permission)]
    if missing:
        raise PermissionDenied("You do not have permission to change subscriptions.")


def _snapshot_from_plan(plan: Plan) -> dict[str, object]:
    return {
        "plan_name": plan.name,
        "download_speed_mbps": plan.download_speed_mbps,
        "price_minor": plan.price_minor,
        "currency": plan.currency,
        "duration_days": plan.duration_days,
        "grace_period_hours": plan.grace_period_hours,
    }


def _subscription_metadata(subscription: Subscription) -> dict[str, object]:
    return {
        "service_reference": subscription.service.service_reference,
        "subscription_id": str(subscription.pk),
        "plan_id": str(subscription.plan_id),
        "plan_name": subscription.plan_name,
        "price_minor": subscription.price_minor,
        "download_speed_mbps": subscription.download_speed_mbps,
    }


def _status_transition(old_status: str, new_status: str) -> dict[str, str]:
    return {"from": old_status, "to": new_status}


def _create_active_subscription(
    *,
    service: Service,
    plan: Plan,
    starts_at,
) -> Subscription:
    return Subscription(
        service=service,
        plan=plan,
        status=Subscription.STATUS_ACTIVE,
        starts_at=starts_at,
        ended_at=None,
        **_snapshot_from_plan(plan),
    )


def _save_new_subscription(subscription: Subscription) -> Subscription:
    try:
        with transaction.atomic():
            subscription.save()
    except IntegrityError as exc:
        raise ValidationError("This service already has an active subscription.") from exc
    return subscription


def _active_subscription_for_service(service: Service) -> Subscription | None:
    return (
        Subscription.objects.select_for_update()
        .select_related("service", "plan")
        .filter(service=service, status=Subscription.STATUS_ACTIVE)
        .first()
    )


@transaction.atomic
def create_package(*, form, actor, request: HttpRequest | None = None) -> Plan:
    plan = form.save()
    record_event(
        action="package.created",
        actor=actor,
        request=request,
        target_type="package",
        target_identifier=plan.pk,
        metadata={"changed_fields": AUDITED_FIELDS, "new": snapshot(plan)},
        reason=form.cleaned_data["reason"],
    )
    return plan


@transaction.atomic
def update_package(*, plan: Plan, form, actor, request: HttpRequest | None = None) -> Plan:
    locked_plan = Plan.objects.select_for_update().get(pk=plan.pk)
    old = snapshot(locked_plan)
    for field in [
        "name",
        "download_speed_mbps",
        "duration_days",
        "grace_period_hours",
        "description",
    ]:
        setattr(locked_plan, field, form.cleaned_data[field])
    locked_plan.price_minor = form.cleaned_data["price_ksh"]
    locked_plan.currency = "KES"
    locked_plan.save()
    record_event(
        action="package.updated",
        actor=actor,
        request=request,
        target_type="package",
        target_identifier=locked_plan.pk,
        metadata=changed_metadata(old, locked_plan),
        reason=form.cleaned_data["reason"],
    )
    return locked_plan


@transaction.atomic
def set_package_active(
    *,
    plan: Plan,
    is_active: bool,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Plan:
    locked_plan = Plan.objects.select_for_update().get(pk=plan.pk)
    old = snapshot(locked_plan)
    locked_plan.is_active = is_active
    locked_plan.save(update_fields=["is_active", "updated_at"])
    record_event(
        action="package.reactivated" if is_active else "package.deactivated",
        actor=actor,
        request=request,
        target_type="package",
        target_identifier=locked_plan.pk,
        metadata=changed_metadata(old, locked_plan),
        reason=reason,
    )
    return locked_plan


@transaction.atomic
def assign_package(
    *,
    service: Service,
    plan: Plan,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Subscription:
    _require_permission(actor, "subscribers.view_service", "billing.add_subscription")
    locked_service = (
        Service.objects.select_for_update().select_related("subscriber").get(pk=service.pk)
    )
    locked_plan = Plan.objects.select_for_update().get(pk=plan.pk)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    if not locked_plan.is_active:
        raise ValidationError("Only active packages can be assigned.")
    if not locked_service.is_active:
        raise ValidationError("Only active services can receive package assignments.")
    if not locked_service.subscriber.is_active:
        raise ValidationError("Only active subscribers can receive package assignments.")
    if _active_subscription_for_service(locked_service) is not None:
        raise ValidationError("This service already has an active subscription.")

    effective_at = timezone.now()
    subscription = _save_new_subscription(
        _create_active_subscription(
            service=locked_service,
            plan=locked_plan,
            starts_at=effective_at,
        )
    )
    record_event(
        action="subscription.assigned",
        actor=actor,
        request=request,
        target_type="subscription",
        target_identifier=subscription.pk,
        metadata={
            **_subscription_metadata(subscription),
            "status_transition": _status_transition("none", Subscription.STATUS_ACTIVE),
            "effective_timestamp": effective_at.isoformat(),
            "changed_fields": ["status", "starts_at", *SUBSCRIPTION_SNAPSHOT_FIELDS],
        },
        reason=reason,
    )
    return subscription


@transaction.atomic
def change_subscription_package(
    *,
    subscription: Subscription,
    plan: Plan,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Subscription:
    _require_permission(actor, "subscribers.view_service", "billing.change_subscription")
    locked_subscription = (
        Subscription.objects.select_for_update()
        .select_related("service", "service__subscriber", "plan")
        .get(pk=subscription.pk)
    )
    locked_service = (
        Service.objects.select_for_update()
        .select_related("subscriber")
        .get(pk=locked_subscription.service_id)
    )
    locked_plan = Plan.objects.select_for_update().get(pk=plan.pk)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    if locked_subscription.status != Subscription.STATUS_ACTIVE:
        raise ValidationError("Only active subscriptions can be changed.")
    if locked_subscription.plan_id == locked_plan.pk:
        raise ValidationError("Choose a different active package.")
    if not locked_plan.is_active:
        raise ValidationError("Only active packages can be assigned.")
    if not locked_service.is_active:
        raise ValidationError("Only active services can receive package changes.")
    if not locked_service.subscriber.is_active:
        raise ValidationError("Only active subscribers can receive package changes.")

    active_subscription = _active_subscription_for_service(locked_service)
    if active_subscription is None or active_subscription.pk != locked_subscription.pk:
        raise ValidationError("The selected subscription is no longer active.")

    effective_at = timezone.now()
    old_subscription_id = str(locked_subscription.pk)
    locked_subscription.status = Subscription.STATUS_ENDED
    locked_subscription.ended_at = effective_at
    locked_subscription.save(update_fields=["status", "ended_at", "updated_at"])
    new_subscription = _save_new_subscription(
        _create_active_subscription(
            service=locked_service,
            plan=locked_plan,
            starts_at=effective_at,
        )
    )
    record_event(
        action="subscription.package_changed",
        actor=actor,
        request=request,
        target_type="subscription",
        target_identifier=new_subscription.pk,
        metadata={
            **_subscription_metadata(new_subscription),
            "old_subscription_id": old_subscription_id,
            "status_transition": _status_transition(
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_ENDED,
            ),
            "new_status": Subscription.STATUS_ACTIVE,
            "effective_timestamp": effective_at.isoformat(),
            "changed_fields": [
                "plan",
                "status",
                "ended_at",
                "starts_at",
                *SUBSCRIPTION_SNAPSHOT_FIELDS,
            ],
        },
        reason=reason,
    )
    return new_subscription


@transaction.atomic
def end_subscription(
    *,
    subscription: Subscription,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> Subscription:
    _require_permission(actor, "subscribers.view_service", "billing.change_subscription")
    locked_subscription = (
        Subscription.objects.select_for_update()
        .select_related("service", "service__subscriber", "plan")
        .get(pk=subscription.pk)
    )
    Service.objects.select_for_update().get(pk=locked_subscription.service_id)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    if locked_subscription.status != Subscription.STATUS_ACTIVE:
        raise ValidationError("Only active subscriptions can be ended.")

    effective_at = timezone.now()
    locked_subscription.status = Subscription.STATUS_ENDED
    locked_subscription.ended_at = effective_at
    locked_subscription.save(update_fields=["status", "ended_at", "updated_at"])
    record_event(
        action="subscription.ended",
        actor=actor,
        request=request,
        target_type="subscription",
        target_identifier=locked_subscription.pk,
        metadata={
            **_subscription_metadata(locked_subscription),
            "status_transition": _status_transition(
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_ENDED,
            ),
            "effective_timestamp": effective_at.isoformat(),
            "changed_fields": ["status", "ended_at"],
        },
        reason=reason,
    )
    return locked_subscription
