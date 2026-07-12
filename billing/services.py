from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from audit.service import record_event
from subscribers.models import Service

from .models import BillingPeriod, Plan, Subscription

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
BILLING_STATE_UNACTIVATED = "unactivated"
BILLING_STATE_ACTIVE = "active"
BILLING_STATE_GRACE = "grace"
BILLING_STATE_EXPIRED = "expired"
STALE_BILLING_PERIOD_MESSAGE = (
    "The billing period changed while this form was open. Refresh and try again."
)


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


def _billing_period_metadata(period: BillingPeriod, state: str) -> dict[str, object]:
    return {
        "service_reference": period.service.service_reference,
        "subscription_id": str(period.subscription_id),
        "billing_period_id": str(period.pk),
        "sequence_number": period.sequence_number,
        "period_type": period.period_type,
        "previous_period_id": str(period.previous_period_id) if period.previous_period_id else "",
        "plan_name": period.plan_name,
        "download_speed_mbps": period.download_speed_mbps,
        "price_minor": period.price_minor,
        "duration_days": period.duration_days,
        "grace_period_hours": period.grace_period_hours,
        "effective_timestamp": period.effective_at.isoformat(),
        "starts_at": period.starts_at.isoformat(),
        "expires_at": period.expires_at.isoformat(),
        "grace_until": period.grace_until.isoformat(),
        "derived_state": state,
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


def _is_active_subscription_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name == "billing_subscription_one_active_per_service":
        return True

    message = str(error).lower()
    return (
        "unique" in message
        and "billing_subscription" in message
        and "service_id" in message
    )


def _is_active_subscription_validation_conflict(error: ValidationError) -> bool:
    return "billing_subscription_one_active_per_service" in str(error)


def _save_new_subscription(subscription: Subscription) -> Subscription:
    try:
        with transaction.atomic():
            subscription.save()
    except ValidationError as exc:
        if not _is_active_subscription_validation_conflict(exc):
            raise
        raise ValidationError("This service already has an active subscription.") from exc
    except IntegrityError as exc:
        if not _is_active_subscription_conflict(exc):
            raise
        raise ValidationError("This service already has an active subscription.") from exc
    return subscription


def _lock_service_and_subscriber_by_id(service_id: UUID) -> Service:
    # Lock subscriptions service-first: service/subscriber, active subscription, package.
    return (
        Service.objects.select_related("subscriber")
        .select_for_update(of=("self", "subscriber"))
        .get(pk=service_id)
    )


def _lock_service_and_subscriber(service: Service) -> Service:
    return _lock_service_and_subscriber_by_id(service.pk)


def _lock_current_active_subscription(service: Service) -> Subscription | None:
    return (
        Subscription.objects.select_for_update(of=("self",))
        .filter(service_id=service.pk, status=Subscription.STATUS_ACTIVE)
        .first()
    )


def _lock_latest_billing_period(service: Service) -> BillingPeriod | None:
    return (
        BillingPeriod.objects.select_for_update(of=("self",))
        .filter(service_id=service.pk)
        .order_by("-sequence_number")
        .first()
    )


def _lock_selected_plan(plan: Plan) -> Plan:
    return Plan.objects.select_for_update(of=("self",)).get(pk=plan.pk)


def _lookup_subscription_service_id(subscription: Subscription) -> UUID:
    return Subscription.objects.only("service_id").get(pk=subscription.pk).service_id


def _normalize_operation_id(operation_id) -> UUID:
    try:
        return operation_id if isinstance(operation_id, UUID) else UUID(str(operation_id))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Operation ID is not valid.") from exc


def _normalize_expected_previous_period_id(expected_previous_period_id) -> UUID | None:
    if expected_previous_period_id in {None, ""}:
        return None
    try:
        return (
            expected_previous_period_id
            if isinstance(expected_previous_period_id, UUID)
            else UUID(str(expected_previous_period_id))
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Expected previous billing period is not valid.") from exc


def _validate_reason(reason: str) -> str:
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    return reason


def _validate_aware_timestamp(value, field_name: str):
    if timezone.is_naive(value):
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return value


def _period_snapshot_from_subscription(subscription: Subscription) -> dict[str, object]:
    return {
        "plan_name": subscription.plan_name,
        "download_speed_mbps": subscription.download_speed_mbps,
        "price_minor": subscription.price_minor,
        "currency": subscription.currency,
        "duration_days": subscription.duration_days,
        "grace_period_hours": subscription.grace_period_hours,
    }


def _billing_period_state(latest_period: BillingPeriod | None, at_time) -> str:
    _validate_aware_timestamp(at_time, "State timestamp")
    if latest_period is None:
        return BILLING_STATE_UNACTIVATED
    if at_time < latest_period.expires_at:
        return BILLING_STATE_ACTIVE
    if at_time < latest_period.grace_until:
        return BILLING_STATE_GRACE
    return BILLING_STATE_EXPIRED


def billing_state_for_service(service: Service, at_time=None) -> str:
    at_time = at_time or timezone.now()
    latest_period = (
        BillingPeriod.objects.filter(service_id=service.pk).order_by("-sequence_number").first()
    )
    return _billing_period_state(latest_period, at_time)


def _existing_operation_result(
    *,
    service: Service,
    operation_id: UUID,
    period_type: str,
    expected_previous_period_id: UUID | None,
) -> BillingPeriod | None:
    period = (
        BillingPeriod.objects.select_related("service", "subscription", "previous_period")
        .filter(operation_id=operation_id)
        .first()
    )
    if period is None:
        return None
    if (
        period.service_id == service.pk
        and period.period_type == period_type
        and period.previous_period_id == expected_previous_period_id
    ):
        return period
    raise ValidationError("Operation ID was already used for a different billing period.")


def _is_billing_period_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name in {
        "billing_period_service_sequence_unique",
        "billing_period_previous_single_successor",
        "billing_billingperiod_operation_id_key",
    }:
        return True
    message = str(error).lower()
    return "billing_period" in message and ("unique" in message or "duplicate" in message)


def _save_billing_period(period: BillingPeriod) -> BillingPeriod:
    try:
        period.save()
    except IntegrityError as exc:
        if not _is_billing_period_conflict(exc):
            raise
        raise ValidationError(STALE_BILLING_PERIOD_MESSAGE) from exc
    return period


def _assert_billing_period_eligibility(
    *,
    service: Service,
    subscription: Subscription | None,
    action: str,
) -> Subscription:
    if not service.is_active:
        raise ValidationError(f"Only active services can be {action}.")
    if not service.subscriber.is_active:
        raise ValidationError(f"Only active subscribers can be {action}.")
    if subscription is None:
        raise ValidationError("A current active subscription is required.")
    subscription.service = service
    return subscription


def _create_billing_period(
    *,
    service: Service,
    subscription: Subscription,
    sequence_number: int,
    period_type: str,
    operation_id: UUID,
    previous_period: BillingPeriod | None,
    effective_at,
) -> BillingPeriod:
    if previous_period is None:
        starts_at = effective_at
    elif effective_at < previous_period.grace_until:
        starts_at = previous_period.expires_at
    else:
        starts_at = effective_at
    expires_at = starts_at + timedelta(days=subscription.duration_days)
    grace_until = expires_at + timedelta(hours=subscription.grace_period_hours)
    return BillingPeriod(
        service=service,
        subscription=subscription,
        sequence_number=sequence_number,
        period_type=period_type,
        operation_id=operation_id,
        previous_period=previous_period,
        effective_at=effective_at,
        starts_at=starts_at,
        expires_at=expires_at,
        grace_until=grace_until,
        **_period_snapshot_from_subscription(subscription),
    )


def _record_billing_period_event(
    *,
    action: str,
    period: BillingPeriod,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="billing_period",
        target_identifier=period.pk,
        metadata=_billing_period_metadata(period, billing_state_for_service(period.service)),
        reason=reason,
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
    locked_service = _lock_service_and_subscriber(service)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    if not locked_service.is_active:
        raise ValidationError("Only active services can receive package assignments.")
    if not locked_service.subscriber.is_active:
        raise ValidationError("Only active subscribers can receive package assignments.")
    if _lock_current_active_subscription(locked_service) is not None:
        raise ValidationError("This service already has an active subscription.")
    locked_plan = _lock_selected_plan(plan)
    if not locked_plan.is_active:
        raise ValidationError("Only active packages can be assigned.")

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
    service_id = _lookup_subscription_service_id(subscription)
    locked_service = _lock_service_and_subscriber_by_id(service_id)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    locked_subscription = _lock_current_active_subscription(locked_service)
    if locked_subscription is None or locked_subscription.pk != subscription.pk:
        raise ValidationError("The selected subscription is no longer active.")
    if locked_subscription.service_id != locked_service.pk:
        raise ValidationError("The selected subscription no longer belongs to this service.")
    locked_subscription.service = locked_service
    locked_plan = _lock_selected_plan(plan)
    if locked_subscription.plan_id == locked_plan.pk:
        raise ValidationError("Choose a different active package.")
    if not locked_plan.is_active:
        raise ValidationError("Only active packages can be assigned.")
    if not locked_service.is_active:
        raise ValidationError("Only active services can receive package changes.")
    if not locked_service.subscriber.is_active:
        raise ValidationError("Only active subscribers can receive package changes.")

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
    service_id = _lookup_subscription_service_id(subscription)
    locked_service = _lock_service_and_subscriber_by_id(service_id)
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    locked_subscription = _lock_current_active_subscription(locked_service)
    if locked_subscription is None or locked_subscription.pk != subscription.pk:
        raise ValidationError("The selected subscription is no longer active.")
    if locked_subscription.service_id != locked_service.pk:
        raise ValidationError("The selected subscription no longer belongs to this service.")
    locked_subscription.service = locked_service

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


@transaction.atomic
def activate_billing_period(
    *,
    service: Service,
    operation_id,
    expected_previous_period_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
    effective_at=None,
) -> BillingPeriod:
    _require_permission(actor, "subscribers.view_service", "billing.add_billingperiod")
    if not actor.has_perm("billing.view_subscription"):
        raise PermissionDenied("You do not have permission to create billing periods.")
    reason = _validate_reason(reason)
    operation_uuid = _normalize_operation_id(operation_id)
    expected_previous_uuid = _normalize_expected_previous_period_id(expected_previous_period_id)
    if expected_previous_uuid is not None:
        raise ValidationError("First activation cannot include a previous billing period.")

    existing = _existing_operation_result(
        service=service,
        operation_id=operation_uuid,
        period_type=BillingPeriod.PERIOD_ACTIVATION,
        expected_previous_period_id=None,
    )
    if existing is not None:
        return existing

    locked_service = _lock_service_and_subscriber(service)
    locked_subscription = _assert_billing_period_eligibility(
        service=locked_service,
        subscription=_lock_current_active_subscription(locked_service),
        action="activated",
    )
    latest_period = _lock_latest_billing_period(locked_service)

    existing = _existing_operation_result(
        service=locked_service,
        operation_id=operation_uuid,
        period_type=BillingPeriod.PERIOD_ACTIVATION,
        expected_previous_period_id=None,
    )
    if existing is not None:
        return existing
    if latest_period is not None:
        raise ValidationError("Billing period history already exists for this service.")

    effective_at = _validate_aware_timestamp(effective_at or timezone.now(), "Effective time")
    period = _save_billing_period(
        _create_billing_period(
            service=locked_service,
            subscription=locked_subscription,
            sequence_number=1,
            period_type=BillingPeriod.PERIOD_ACTIVATION,
            operation_id=operation_uuid,
            previous_period=None,
            effective_at=effective_at,
        )
    )
    _record_billing_period_event(
        action="billing_period.activated",
        period=period,
        actor=actor,
        request=request,
        reason=reason,
    )
    return period


@transaction.atomic
def renew_billing_period(
    *,
    service: Service,
    operation_id,
    expected_previous_period_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
    effective_at=None,
) -> BillingPeriod:
    _require_permission(actor, "subscribers.view_service", "billing.add_billingperiod")
    if not actor.has_perm("billing.view_subscription"):
        raise PermissionDenied("You do not have permission to create billing periods.")
    reason = _validate_reason(reason)
    operation_uuid = _normalize_operation_id(operation_id)
    expected_previous_uuid = _normalize_expected_previous_period_id(expected_previous_period_id)
    if expected_previous_uuid is None:
        raise ValidationError("Renewal requires the latest billing period.")

    existing = _existing_operation_result(
        service=service,
        operation_id=operation_uuid,
        period_type=BillingPeriod.PERIOD_RENEWAL,
        expected_previous_period_id=expected_previous_uuid,
    )
    if existing is not None:
        return existing

    locked_service = _lock_service_and_subscriber(service)
    locked_subscription = _assert_billing_period_eligibility(
        service=locked_service,
        subscription=_lock_current_active_subscription(locked_service),
        action="renewed",
    )
    latest_period = _lock_latest_billing_period(locked_service)

    existing = _existing_operation_result(
        service=locked_service,
        operation_id=operation_uuid,
        period_type=BillingPeriod.PERIOD_RENEWAL,
        expected_previous_period_id=expected_previous_uuid,
    )
    if existing is not None:
        return existing
    if latest_period is None:
        raise ValidationError("Renewal requires an existing billing period.")
    if latest_period.pk != expected_previous_uuid:
        raise ValidationError(STALE_BILLING_PERIOD_MESSAGE)

    effective_at = _validate_aware_timestamp(effective_at or timezone.now(), "Effective time")
    period = _save_billing_period(
        _create_billing_period(
            service=locked_service,
            subscription=locked_subscription,
            sequence_number=latest_period.sequence_number + 1,
            period_type=BillingPeriod.PERIOD_RENEWAL,
            operation_id=operation_uuid,
            previous_period=latest_period,
            effective_at=effective_at,
        )
    )
    _record_billing_period_event(
        action="billing_period.renewed",
        period=period,
        actor=actor,
        request=request,
        reason=reason,
    )
    return period
