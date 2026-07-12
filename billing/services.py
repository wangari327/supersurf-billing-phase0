from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from audit.service import record_event
from subscribers.models import Service, Subscriber

from .models import (
    MAX_MONEY_MINOR,
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    Payment,
    PaymentAllocation,
    PaymentProviderProfile,
    Plan,
    Subscription,
    UnmatchedPaymentCase,
    Wallet,
)
from .money import ksh_to_minor_units

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
STALE_LEDGER_MESSAGE = "The wallet ledger changed while this form was open. Refresh and try again."
STALE_PAYMENT_MESSAGE = "The payment changed while this form was open. Refresh and try again."
ACCOUNT_REFERENCE_RE = re.compile(r"^SS\d{6}$")


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


def _ledger_entry_metadata(entry: LedgerEntry) -> dict[str, object]:
    return {
        "subscriber_account_number": entry.wallet.subscriber.account_number,
        "wallet_id": str(entry.wallet_id),
        "ledger_entry_id": str(entry.pk),
        "sequence_number": entry.sequence_number,
        "entry_type": entry.entry_type,
        "direction": entry.direction,
        "amount_minor": entry.amount_minor,
        "balance_after_minor": entry.balance_after_minor,
        "currency": entry.currency,
        "reversed_entry_id": str(entry.reverses_entry_id) if entry.reverses_entry_id else "",
        "created_at": entry.created_at.isoformat() if entry.created_at else "",
    }


def _billing_charge_metadata(charge: BillingCharge) -> dict[str, object]:
    period = charge.billing_period
    ledger_entry = charge.ledger_entry
    return {
        "subscriber_account_number": charge.service.subscriber.account_number,
        "service_reference": charge.service.service_reference,
        "wallet_id": str(charge.wallet_id),
        "subscription_id": str(charge.subscription_id),
        "billing_period_id": str(charge.billing_period_id),
        "billing_charge_id": str(charge.pk),
        "ledger_entry_id": str(charge.ledger_entry_id),
        "charge_type": charge.charge_type,
        "amount_minor": charge.amount_minor,
        "balance_after_minor": ledger_entry.balance_after_minor,
        "currency": charge.currency,
        "effective_timestamp": period.effective_at.isoformat(),
        "starts_at": period.starts_at.isoformat(),
        "expires_at": period.expires_at.isoformat(),
        "grace_until": period.grace_until.isoformat(),
        "ledger_sequence_number": ledger_entry.sequence_number,
        "period_sequence_number": period.sequence_number,
    }


def _payment_metadata(payment: Payment) -> dict[str, object]:
    metadata: dict[str, object] = {
        "payment_id": str(payment.pk),
        "provider_profile_id": str(payment.provider_profile_id),
        "provider_name": payment.provider_profile.name,
        "provider": payment.provider_profile.provider,
        "product_type": payment.provider_profile.product_type,
        "provider_transaction_id": payment.provider_transaction_id,
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "received_at": payment.received_at.isoformat(),
    }
    if ACCOUNT_REFERENCE_RE.fullmatch(payment.account_reference):
        metadata["account_reference"] = payment.account_reference
    return metadata


def _payment_allocation_metadata(allocation: PaymentAllocation) -> dict[str, object]:
    entry = allocation.ledger_entry
    return {
        **_payment_metadata(allocation.payment),
        "subscriber_account_number": allocation.wallet.subscriber.account_number,
        "wallet_id": str(allocation.wallet_id),
        "allocation_id": str(allocation.pk),
        "ledger_entry_id": str(allocation.ledger_entry_id),
        "amount_minor": allocation.amount_minor,
        "balance_after_minor": entry.balance_after_minor,
        "currency": allocation.currency,
        "ledger_sequence_number": entry.sequence_number,
    }


def _unmatched_case_metadata(case: UnmatchedPaymentCase) -> dict[str, object]:
    metadata = {
        **_payment_metadata(case.payment),
        "unmatched_payment_case_id": str(case.pk),
        "unmatched_reason_code": case.reason_code,
        "status": case.status,
    }
    if case.resolved_wallet_id:
        metadata["wallet_id"] = str(case.resolved_wallet_id)
        metadata["subscriber_account_number"] = case.resolved_wallet.subscriber.account_number
    if case.resolution_allocation_id:
        metadata["allocation_id"] = str(case.resolution_allocation_id)
    return metadata


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


def _lock_subscriber(subscriber: Subscriber) -> Subscriber:
    return Subscriber.objects.select_for_update(of=("self",)).get(pk=subscriber.pk)


def _lock_wallet(wallet: Wallet) -> Wallet:
    return Wallet.objects.select_for_update(of=("self",)).select_related("subscriber").get(
        pk=wallet.pk
    )


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


def _normalize_ledger_direction(direction: str) -> str:
    direction = str(direction).strip()
    if direction not in {LedgerEntry.DIRECTION_CREDIT, LedgerEntry.DIRECTION_DEBIT}:
        raise ValidationError("Wallet adjustment direction is not valid.")
    return direction


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


def _validate_ledger_reason(reason: str) -> str:
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason is required.")
    if len(reason) > 240:
        raise ValidationError("Reason must be 240 characters or fewer.")
    return reason


def _normalize_ledger_amount(amount) -> int:
    amount_minor = ksh_to_minor_units(amount)
    if amount_minor > MAX_MONEY_MINOR:
        raise ValidationError("Amount is too large.")
    return amount_minor


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


def _existing_charge_operation_result(
    *,
    service: Service,
    operation_id: UUID,
    charge_type: str,
    expected_previous_period_id: UUID | None,
    reason: str,
) -> BillingCharge | None:
    charge = (
        BillingCharge.objects.select_related(
            "service",
            "subscription",
            "billing_period",
            "ledger_entry",
        )
        .filter(operation_id=operation_id)
        .first()
    )
    if charge is not None:
        if (
            charge.service_id == service.pk
            and charge.charge_type == charge_type
            and charge.billing_period.previous_period_id == expected_previous_period_id
            and charge.amount_minor == charge.billing_period.price_minor
            and charge.reason == reason
        ):
            return charge
        raise ValidationError("Operation ID was already used for a different billing charge.")
    if BillingPeriod.objects.filter(operation_id=operation_id).exists():
        raise ValidationError("Operation ID was already used for a different billing period.")
    if LedgerEntry.objects.filter(operation_id=operation_id).exists():
        raise ValidationError("Operation ID was already used for a different ledger entry.")
    return None


def _normalize_account_reference(account_reference) -> str:
    if account_reference is None:
        return ""
    return str(account_reference).strip().upper()


def _normalize_payload_digest(payload_digest) -> str:
    if payload_digest is None:
        return ""
    digest = str(payload_digest).strip().lower()
    if digest and not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValidationError("Payload digest must be a SHA-256 hexadecimal digest.")
    return digest


def _unmatched_reason_code(account_reference: str) -> str:
    if not account_reference:
        return UnmatchedPaymentCase.REASON_MISSING_REFERENCE
    if not ACCOUNT_REFERENCE_RE.fullmatch(account_reference):
        return UnmatchedPaymentCase.REASON_INVALID_REFERENCE
    return UnmatchedPaymentCase.REASON_SUBSCRIBER_NOT_FOUND


def _lock_provider_profile(profile: PaymentProviderProfile) -> PaymentProviderProfile:
    return PaymentProviderProfile.objects.select_for_update(of=("self",)).get(pk=profile.pk)


def _assert_fake_profile_can_ingest(profile: PaymentProviderProfile) -> None:
    if settings.SUPERSURF_ENVIRONMENT == "PRODUCTION":
        raise ValidationError("Fake payment ingestion is prohibited in production.")
    if not profile.is_active:
        raise ValidationError("Payment provider profile is inactive.")
    if profile.provider != PaymentProviderProfile.PROVIDER_FAKE:
        raise ValidationError("Only fake provider profiles may ingest payments in Phase 8.")
    if profile.product_type != PaymentProviderProfile.PRODUCT_FAKE:
        raise ValidationError("Only fake product profiles may ingest payments in Phase 8.")
    if profile.environment not in {
        PaymentProviderProfile.ENVIRONMENT_TEST,
        PaymentProviderProfile.ENVIRONMENT_SANDBOX,
    }:
        raise ValidationError("Fake payment ingestion requires a test or sandbox profile.")


def _assert_payment_equivalent(
    *,
    payment: Payment,
    amount_minor: int,
    received_at,
    account_reference: str,
    payload_digest: str,
) -> None:
    if (
        payment.amount_minor != amount_minor
        or payment.currency != "KES"
        or payment.received_at != received_at
        or payment.account_reference != account_reference
        or payment.payload_digest != payload_digest
    ):
        raise ValidationError("Provider transaction ID was already used differently.")


def _find_locked_payment(
    *,
    provider_profile: PaymentProviderProfile,
    provider_transaction_id: str,
) -> Payment | None:
    return (
        Payment.objects.select_for_update(of=("self",))
        .select_related("provider_profile")
        .filter(
            provider_profile=provider_profile,
            provider_transaction_id=provider_transaction_id,
        )
        .first()
    )


def _operation_id_used_elsewhere(operation_id: UUID) -> str:
    if LedgerEntry.objects.filter(operation_id=operation_id).exists():
        return "ledger entry"
    if PaymentAllocation.objects.filter(operation_id=operation_id).exists():
        return "payment allocation"
    if BillingPeriod.objects.filter(operation_id=operation_id).exists():
        return "billing period"
    if BillingCharge.objects.filter(operation_id=operation_id).exists():
        return "billing charge"
    return ""


def _reject_operation_id_conflicts(operation_id: UUID) -> None:
    used_by = _operation_id_used_elsewhere(operation_id)
    if used_by:
        raise ValidationError(f"Operation ID was already used for a different {used_by}.")


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


def _is_ledger_operation_validation_conflict(error: ValidationError) -> bool:
    return "operation_id" in getattr(error, "error_dict", {})


def _is_ledger_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name in {
        "ledger_entry_wallet_sequence_unique",
        "ledger_entry_previous_single_successor",
        "billing_ledgerentry_operation_id_key",
        "billing_ledgerentry_reverses_entry_id_key",
    }:
        return True
    message = str(error).lower()
    return "ledger" in message and ("unique" in message or "duplicate" in message)


def _is_billing_charge_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name in {
        "billing_billingcharge_operation_id_key",
        "billing_billingcharge_billing_period_id_key",
        "billing_billingcharge_ledger_entry_id_key",
    }:
        return True
    message = str(error).lower()
    return "billingcharge" in message or (
        "billing_charge" in message and ("unique" in message or "duplicate" in message)
    )


def _is_payment_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name in {
        "payment_provider_transaction_unique",
        "billing_payment_provider_profile_id_provider_transaction_id_key",
    }:
        return True
    message = str(error).lower()
    return "payment" in message and ("unique" in message or "duplicate" in message)


def _is_payment_allocation_conflict(error: IntegrityError) -> bool:
    diag = getattr(getattr(error, "__cause__", None), "diag", None)
    constraint_name = getattr(diag, "constraint_name", "")
    if constraint_name in {
        "one_allocation_per_payment",
        "billing_paymentallocation_operation_id_key",
        "billing_paymentallocation_ledger_entry_id_key",
    }:
        return True
    message = str(error).lower()
    return "paymentallocation" in message or (
        "payment_allocation" in message and ("unique" in message or "duplicate" in message)
    )


def _save_billing_period(period: BillingPeriod) -> BillingPeriod:
    try:
        period.save()
    except IntegrityError as exc:
        if not _is_billing_period_conflict(exc):
            raise
        raise ValidationError(STALE_BILLING_PERIOD_MESSAGE) from exc
    return period


def _save_wallet(wallet: Wallet) -> Wallet:
    try:
        wallet.save()
    except IntegrityError as exc:
        message = str(exc).lower()
        if "wallet" not in message or "unique" not in message:
            raise
        raise ValidationError("This subscriber already has a wallet.") from exc
    return wallet


def _save_ledger_entry(entry: LedgerEntry) -> LedgerEntry:
    try:
        entry.save()
    except ValidationError as exc:
        if not _is_ledger_operation_validation_conflict(exc):
            raise
        raise ValidationError(
            "Operation ID was already used for a different ledger entry."
        ) from exc
    except IntegrityError as exc:
        if not _is_ledger_conflict(exc):
            raise
        raise ValidationError(STALE_LEDGER_MESSAGE) from exc
    return entry


def _save_billing_charge(charge: BillingCharge) -> BillingCharge:
    try:
        charge.save()
    except ValidationError as exc:
        if "operation_id" not in getattr(exc, "error_dict", {}):
            raise
        raise ValidationError(
            "Operation ID was already used for a different billing charge."
        ) from exc
    except IntegrityError as exc:
        if not _is_billing_charge_conflict(exc):
            raise
        raise ValidationError("The billing charge changed while this form was open.") from exc
    return charge


def _create_payment_or_get_existing(payment: Payment) -> tuple[Payment, bool]:
    try:
        with transaction.atomic():
            payment.save()
    except ValidationError:
        existing = _find_locked_payment(
            provider_profile=payment.provider_profile,
            provider_transaction_id=payment.provider_transaction_id,
        )
        if existing is not None:
            return existing, False
        raise
    except IntegrityError as exc:
        if not _is_payment_conflict(exc):
            raise
        existing = _find_locked_payment(
            provider_profile=payment.provider_profile,
            provider_transaction_id=payment.provider_transaction_id,
        )
        if existing is None:
            raise ValidationError(STALE_PAYMENT_MESSAGE) from exc
        return existing, False
    return payment, True


def _save_payment_allocation(allocation: PaymentAllocation) -> PaymentAllocation:
    try:
        allocation.save()
    except ValidationError as exc:
        if "operation_id" not in getattr(exc, "error_dict", {}):
            raise
        raise ValidationError(
            "Operation ID was already used for a different payment allocation."
        ) from exc
    except IntegrityError as exc:
        if not _is_payment_allocation_conflict(exc):
            raise
        raise ValidationError(STALE_PAYMENT_MESSAGE) from exc
    return allocation


def _save_unmatched_case(case: UnmatchedPaymentCase) -> UnmatchedPaymentCase:
    try:
        case.save()
    except IntegrityError as exc:
        message = str(exc).lower()
        if "unmatched" not in message or "unique" not in message:
            raise
        raise ValidationError(STALE_PAYMENT_MESSAGE) from exc
    return case


def _get_or_create_locked_wallet(subscriber: Subscriber) -> Wallet:
    try:
        return Wallet.objects.select_for_update(of=("self",)).get(subscriber=subscriber)
    except Wallet.DoesNotExist:
        return _save_wallet(Wallet(subscriber=subscriber))


def _lock_existing_wallet(subscriber: Subscriber) -> Wallet:
    try:
        return Wallet.objects.select_for_update(of=("self",)).get(subscriber=subscriber)
    except Wallet.DoesNotExist as exc:
        raise ValidationError("An existing wallet is required for Wallet-funded billing.") from exc


def _lock_latest_ledger_entry(wallet: Wallet) -> LedgerEntry | None:
    return (
        LedgerEntry.objects.select_for_update(of=("self",))
        .filter(wallet_id=wallet.pk)
        .order_by("-sequence_number")
        .first()
    )


def _ledger_current_balance(latest_entry: LedgerEntry | None) -> int:
    if latest_entry is None:
        return 0
    return latest_entry.balance_after_minor


def _ledger_next_sequence(latest_entry: LedgerEntry | None) -> int:
    if latest_entry is None:
        return 1
    return latest_entry.sequence_number + 1


def _ledger_resulting_balance(*, current_balance: int, direction: str, amount_minor: int) -> int:
    if direction == LedgerEntry.DIRECTION_CREDIT:
        result = current_balance + amount_minor
    else:
        result = current_balance - amount_minor
    if result < 0:
        raise ValidationError("Wallet balance cannot become negative.")
    if result > MAX_MONEY_MINOR:
        raise ValidationError("Wallet balance is too large.")
    return result


def _manual_entry_type(direction: str) -> str:
    if direction == LedgerEntry.DIRECTION_CREDIT:
        return LedgerEntry.ENTRY_MANUAL_CREDIT
    return LedgerEntry.ENTRY_MANUAL_DEBIT


def _opposite_direction(direction: str) -> str:
    if direction == LedgerEntry.DIRECTION_CREDIT:
        return LedgerEntry.DIRECTION_DEBIT
    return LedgerEntry.DIRECTION_CREDIT


def _existing_adjustment_operation_result(
    *,
    subscriber: Subscriber,
    operation_id: UUID,
    entry_type: str,
    direction: str,
    amount_minor: int,
    reason: str,
) -> LedgerEntry | None:
    entry = (
        LedgerEntry.objects.select_related("wallet", "wallet__subscriber")
        .filter(operation_id=operation_id)
        .first()
    )
    if entry is None:
        return None
    if (
        entry.wallet.subscriber_id == subscriber.pk
        and entry.entry_type == entry_type
        and entry.direction == direction
        and entry.amount_minor == amount_minor
        and entry.reason == reason
    ):
        return entry
    raise ValidationError("Operation ID was already used for a different ledger entry.")


def _existing_reversal_operation_result(
    *,
    target: LedgerEntry,
    operation_id: UUID,
    direction: str,
    reason: str,
) -> LedgerEntry | None:
    entry = (
        LedgerEntry.objects.select_related("wallet", "wallet__subscriber", "reverses_entry")
        .filter(operation_id=operation_id)
        .first()
    )
    if entry is None:
        return None
    if (
        entry.entry_type == LedgerEntry.ENTRY_REVERSAL
        and entry.reverses_entry_id == target.pk
        and entry.amount_minor == target.amount_minor
        and entry.direction == direction
        and entry.reason == reason
    ):
        return entry
    raise ValidationError("Operation ID was already used for a different ledger entry.")


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


def _record_ledger_event(
    *,
    action: str,
    entry: LedgerEntry,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="ledger_entry",
        target_identifier=entry.pk,
        metadata=_ledger_entry_metadata(entry),
        reason=reason,
    )


def _record_billing_charge_event(
    *,
    action: str,
    charge: BillingCharge,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="billing_charge",
        target_identifier=charge.pk,
        metadata=_billing_charge_metadata(charge),
        reason=reason,
    )


def _record_payment_event(
    *,
    action: str,
    payment: Payment,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="payment",
        target_identifier=payment.pk,
        metadata=_payment_metadata(payment),
        reason=reason,
    )


def _record_payment_allocation_event(
    *,
    action: str,
    allocation: PaymentAllocation,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="payment_allocation",
        target_identifier=allocation.pk,
        metadata=_payment_allocation_metadata(allocation),
        reason=reason,
    )


def _record_unmatched_case_event(
    *,
    action: str,
    case: UnmatchedPaymentCase,
    actor,
    request: HttpRequest | None,
    reason: str,
) -> None:
    record_event(
        action=action,
        actor=actor,
        request=request,
        target_type="unmatched_payment_case",
        target_identifier=case.pk,
        metadata=_unmatched_case_metadata(case),
        reason=reason,
    )


def _payment_mutation_permissions(actor) -> None:
    _require_permission(
        actor,
        "subscribers.view_subscriber",
        "billing.view_paymentproviderprofile",
        "billing.view_payment",
        "billing.add_payment",
        "billing.view_paymentallocation",
        "billing.add_paymentallocation",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
    )


def _unmatched_resolution_permissions(actor) -> None:
    _require_permission(
        actor,
        "subscribers.view_subscriber",
        "billing.view_payment",
        "billing.view_paymentallocation",
        "billing.add_paymentallocation",
        "billing.view_unmatchedpaymentcase",
        "billing.change_unmatchedpaymentcase",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
    )


def _create_payment_wallet_credit(
    *,
    payment: Payment,
    subscriber: Subscriber,
    operation_id: UUID,
    actor,
) -> PaymentAllocation:
    wallet = _get_or_create_locked_wallet(subscriber)
    wallet.subscriber = subscriber
    latest_entry = _lock_latest_ledger_entry(wallet)
    balance_after = _ledger_resulting_balance(
        current_balance=_ledger_current_balance(latest_entry),
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount_minor=payment.amount_minor,
    )
    ledger_entry = _save_ledger_entry(
        LedgerEntry(
            wallet=wallet,
            sequence_number=_ledger_next_sequence(latest_entry),
            operation_id=operation_id,
            entry_type=LedgerEntry.ENTRY_PAYMENT_CREDIT,
            direction=LedgerEntry.DIRECTION_CREDIT,
            amount_minor=payment.amount_minor,
            balance_after_minor=balance_after,
            previous_entry=latest_entry,
            reverses_entry=None,
            reason="Payment credit",
            created_by=actor,
        )
    )
    return _save_payment_allocation(
        PaymentAllocation(
            payment=payment,
            wallet=wallet,
            ledger_entry=ledger_entry,
            operation_id=operation_id,
            allocation_type=PaymentAllocation.ALLOCATION_WALLET_CREDIT,
            amount_minor=payment.amount_minor,
            currency="KES",
            created_by=actor,
        )
    )


@transaction.atomic
def ingest_fake_payment(
    *,
    provider_profile: PaymentProviderProfile,
    provider_transaction_id: str,
    amount,
    received_at,
    account_reference,
    operation_id,
    actor,
    payload_digest: str = "",
    request: HttpRequest | None = None,
) -> Payment:
    _payment_mutation_permissions(actor)
    operation_uuid = _normalize_operation_id(operation_id)
    amount_minor = _normalize_ledger_amount(amount)
    received_at = _validate_aware_timestamp(received_at, "Received time")
    provider_transaction_id = str(provider_transaction_id).strip()
    if not provider_transaction_id:
        raise ValidationError("Provider transaction ID is required.")
    normalized_reference = _normalize_account_reference(account_reference)
    payload_digest = _normalize_payload_digest(payload_digest)

    locked_profile = _lock_provider_profile(provider_profile)
    _assert_fake_profile_can_ingest(locked_profile)
    existing = _find_locked_payment(
        provider_profile=locked_profile,
        provider_transaction_id=provider_transaction_id,
    )
    if existing is not None:
        _assert_payment_equivalent(
            payment=existing,
            amount_minor=amount_minor,
            received_at=received_at,
            account_reference=normalized_reference,
            payload_digest=payload_digest,
        )
        return existing

    _reject_operation_id_conflicts(operation_uuid)
    payment, created = _create_payment_or_get_existing(
        Payment(
            provider_profile=locked_profile,
            provider_transaction_id=provider_transaction_id,
            amount_minor=amount_minor,
            currency="KES",
            received_at=received_at,
            account_reference=normalized_reference,
            payload_digest=payload_digest,
        )
    )
    if not created:
        _assert_payment_equivalent(
            payment=payment,
            amount_minor=amount_minor,
            received_at=received_at,
            account_reference=normalized_reference,
            payload_digest=payload_digest,
        )
        return payment

    audit_reason = "Fake payment ingestion"
    _record_payment_event(
        action="payment.received",
        payment=payment,
        actor=actor,
        request=request,
        reason=audit_reason,
    )

    subscriber = None
    if ACCOUNT_REFERENCE_RE.fullmatch(normalized_reference):
        subscriber = (
            Subscriber.objects.select_for_update(of=("self",))
            .filter(account_number=normalized_reference)
            .first()
        )
    if subscriber is None:
        case = _save_unmatched_case(
            UnmatchedPaymentCase(
                payment=payment,
                status=UnmatchedPaymentCase.STATUS_OPEN,
                reason_code=_unmatched_reason_code(normalized_reference),
            )
        )
        _record_unmatched_case_event(
            action="payment.unmatched",
            case=case,
            actor=actor,
            request=request,
            reason=audit_reason,
        )
        return payment

    allocation = _create_payment_wallet_credit(
        payment=payment,
        subscriber=subscriber,
        operation_id=operation_uuid,
        actor=actor,
    )
    _record_payment_allocation_event(
        action="payment.allocated",
        allocation=allocation,
        actor=actor,
        request=request,
        reason=audit_reason,
    )
    _record_ledger_event(
        action="wallet.payment_credit",
        entry=allocation.ledger_entry,
        actor=actor,
        request=request,
        reason=audit_reason,
    )
    return payment


@transaction.atomic
def resolve_unmatched_payment(
    *,
    unmatched_case: UnmatchedPaymentCase,
    subscriber: Subscriber,
    operation_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> PaymentAllocation:
    _unmatched_resolution_permissions(actor)
    operation_uuid = _normalize_operation_id(operation_id)
    reason = _validate_ledger_reason(reason)
    case = (
        UnmatchedPaymentCase.objects.select_for_update(of=("self",))
        .select_related("payment", "resolution_allocation", "resolved_wallet")
        .get(pk=unmatched_case.pk)
    )
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("provider_profile")
        .get(pk=case.payment_id)
    )
    case.payment = payment

    if case.status == UnmatchedPaymentCase.STATUS_RESOLVED:
        allocation = case.resolution_allocation
        if allocation is None:
            allocation = (
                PaymentAllocation.objects.select_related("wallet")
                .filter(payment=payment, operation_id=operation_uuid)
                .first()
            )
        if (
            allocation is not None
            and allocation.operation_id == operation_uuid
            and allocation.payment_id == payment.pk
            and case.resolved_wallet_id == allocation.wallet_id
            and allocation.wallet.subscriber_id == subscriber.pk
            and case.resolution_reason == reason
        ):
            return allocation
        raise ValidationError("This unmatched payment case has already been resolved.")
    if payment.allocations.exists():
        raise ValidationError("Payment has already been allocated.")

    _reject_operation_id_conflicts(operation_uuid)
    locked_subscriber = _lock_subscriber(subscriber)
    allocation = _create_payment_wallet_credit(
        payment=payment,
        subscriber=locked_subscriber,
        operation_id=operation_uuid,
        actor=actor,
    )
    case.status = UnmatchedPaymentCase.STATUS_RESOLVED
    case.resolved_wallet = allocation.wallet
    case.resolution_allocation = allocation
    case.resolution_reason = reason
    case.resolved_by = actor
    case.resolved_at = timezone.now()
    case._allow_resolution_save = True
    case.save(
        update_fields=[
            "status",
            "resolved_wallet",
            "resolution_allocation",
            "resolution_reason",
            "resolved_by",
            "resolved_at",
        ]
    )
    _record_payment_allocation_event(
        action="payment.allocated",
        allocation=allocation,
        actor=actor,
        request=request,
        reason=reason,
    )
    _record_unmatched_case_event(
        action="payment.unmatched_resolved",
        case=case,
        actor=actor,
        request=request,
        reason=reason,
    )
    _record_ledger_event(
        action="wallet.payment_credit",
        entry=allocation.ledger_entry,
        actor=actor,
        request=request,
        reason=reason,
    )
    return allocation


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


def _wallet_charge_permissions(actor) -> None:
    _require_permission(
        actor,
        "subscribers.view_subscriber",
        "subscribers.view_service",
        "billing.view_subscription",
        "billing.view_billingperiod",
        "billing.add_billingperiod",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
        "billing.view_billingcharge",
        "billing.add_billingcharge",
    )


@transaction.atomic
def _post_wallet_funded_period(
    *,
    service: Service,
    operation_id,
    expected_previous_period_id,
    reason: str,
    actor,
    request: HttpRequest | None,
    effective_at,
    charge_type: str,
) -> BillingCharge:
    _wallet_charge_permissions(actor)
    reason = _validate_ledger_reason(reason)
    operation_uuid = _normalize_operation_id(operation_id)
    expected_previous_uuid = _normalize_expected_previous_period_id(expected_previous_period_id)
    if charge_type == BillingCharge.CHARGE_ACTIVATION and expected_previous_uuid is not None:
        raise ValidationError("First activation cannot include a previous billing period.")
    if charge_type == BillingCharge.CHARGE_RENEWAL and expected_previous_uuid is None:
        raise ValidationError("Renewal requires the latest billing period.")

    existing = _existing_charge_operation_result(
        service=service,
        operation_id=operation_uuid,
        charge_type=charge_type,
        expected_previous_period_id=expected_previous_uuid,
        reason=reason,
    )
    if existing is not None:
        return existing

    locked_service = _lock_service_and_subscriber(service)
    wallet = _lock_existing_wallet(locked_service.subscriber)
    wallet.subscriber = locked_service.subscriber
    locked_subscription = _assert_billing_period_eligibility(
        service=locked_service,
        subscription=_lock_current_active_subscription(locked_service),
        action="activated" if charge_type == BillingCharge.CHARGE_ACTIVATION else "renewed",
    )
    latest_period = _lock_latest_billing_period(locked_service)
    latest_entry = _lock_latest_ledger_entry(wallet)

    existing = _existing_charge_operation_result(
        service=locked_service,
        operation_id=operation_uuid,
        charge_type=charge_type,
        expected_previous_period_id=expected_previous_uuid,
        reason=reason,
    )
    if existing is not None:
        return existing

    if charge_type == BillingCharge.CHARGE_ACTIVATION:
        period_type = BillingPeriod.PERIOD_ACTIVATION
        period_action = "billing_period.activated"
        if latest_period is not None:
            raise ValidationError("Billing period history already exists for this service.")
        next_period_sequence = 1
        previous_period = None
    else:
        period_type = BillingPeriod.PERIOD_RENEWAL
        period_action = "billing_period.renewed"
        if latest_period is None:
            raise ValidationError("Renewal requires an existing billing period.")
        if latest_period.pk != expected_previous_uuid:
            raise ValidationError(STALE_BILLING_PERIOD_MESSAGE)
        next_period_sequence = latest_period.sequence_number + 1
        previous_period = latest_period

    amount_minor = locked_subscription.price_minor
    current_balance = _ledger_current_balance(latest_entry)
    if current_balance < amount_minor:
        raise ValidationError("Wallet balance is insufficient for this charge.")
    balance_after = _ledger_resulting_balance(
        current_balance=current_balance,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount_minor=amount_minor,
    )
    effective_at = _validate_aware_timestamp(effective_at or timezone.now(), "Effective time")
    period = _save_billing_period(
        _create_billing_period(
            service=locked_service,
            subscription=locked_subscription,
            sequence_number=next_period_sequence,
            period_type=period_type,
            operation_id=operation_uuid,
            previous_period=previous_period,
            effective_at=effective_at,
        )
    )
    ledger_entry = _save_ledger_entry(
        LedgerEntry(
            wallet=wallet,
            sequence_number=_ledger_next_sequence(latest_entry),
            operation_id=operation_uuid,
            entry_type=LedgerEntry.ENTRY_BILLING_CHARGE,
            direction=LedgerEntry.DIRECTION_DEBIT,
            amount_minor=amount_minor,
            balance_after_minor=balance_after,
            previous_entry=latest_entry,
            reverses_entry=None,
            reason=reason,
            created_by=actor,
        )
    )
    charge = _save_billing_charge(
        BillingCharge(
            service=locked_service,
            subscription=locked_subscription,
            billing_period=period,
            wallet=wallet,
            ledger_entry=ledger_entry,
            operation_id=operation_uuid,
            charge_type=charge_type,
            amount_minor=amount_minor,
            currency="KES",
            reason=reason,
            created_by=actor,
        )
    )
    _record_billing_period_event(
        action=period_action,
        period=period,
        actor=actor,
        request=request,
        reason=reason,
    )
    _record_billing_charge_event(
        action="billing_charge.posted",
        charge=charge,
        actor=actor,
        request=request,
        reason=reason,
    )
    _record_ledger_event(
        action="wallet.billing_charge",
        entry=ledger_entry,
        actor=actor,
        request=request,
        reason=reason,
    )
    return charge


def activate_service_from_wallet(
    *,
    service: Service,
    operation_id,
    expected_previous_period_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
    effective_at=None,
) -> BillingCharge:
    return _post_wallet_funded_period(
        service=service,
        operation_id=operation_id,
        expected_previous_period_id=expected_previous_period_id,
        reason=reason,
        actor=actor,
        request=request,
        effective_at=effective_at,
        charge_type=BillingCharge.CHARGE_ACTIVATION,
    )


def renew_service_from_wallet(
    *,
    service: Service,
    operation_id,
    expected_previous_period_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
    effective_at=None,
) -> BillingCharge:
    return _post_wallet_funded_period(
        service=service,
        operation_id=operation_id,
        expected_previous_period_id=expected_previous_period_id,
        reason=reason,
        actor=actor,
        request=request,
        effective_at=effective_at,
        charge_type=BillingCharge.CHARGE_RENEWAL,
    )


@transaction.atomic
def post_manual_wallet_adjustment(
    *,
    subscriber: Subscriber,
    direction: str,
    amount,
    operation_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> LedgerEntry:
    _require_permission(
        actor,
        "subscribers.view_subscriber",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
    )
    direction = _normalize_ledger_direction(direction)
    amount_minor = _normalize_ledger_amount(amount)
    reason = _validate_ledger_reason(reason)
    operation_uuid = _normalize_operation_id(operation_id)
    entry_type = _manual_entry_type(direction)

    existing = _existing_adjustment_operation_result(
        subscriber=subscriber,
        operation_id=operation_uuid,
        entry_type=entry_type,
        direction=direction,
        amount_minor=amount_minor,
        reason=reason,
    )
    if existing is not None:
        return existing

    locked_subscriber = _lock_subscriber(subscriber)
    wallet = _get_or_create_locked_wallet(locked_subscriber)
    wallet.subscriber = locked_subscriber
    latest_entry = _lock_latest_ledger_entry(wallet)

    existing = _existing_adjustment_operation_result(
        subscriber=locked_subscriber,
        operation_id=operation_uuid,
        entry_type=entry_type,
        direction=direction,
        amount_minor=amount_minor,
        reason=reason,
    )
    if existing is not None:
        return existing

    current_balance = _ledger_current_balance(latest_entry)
    balance_after = _ledger_resulting_balance(
        current_balance=current_balance,
        direction=direction,
        amount_minor=amount_minor,
    )
    entry = _save_ledger_entry(
        LedgerEntry(
            wallet=wallet,
            sequence_number=_ledger_next_sequence(latest_entry),
            operation_id=operation_uuid,
            entry_type=entry_type,
            direction=direction,
            amount_minor=amount_minor,
            balance_after_minor=balance_after,
            previous_entry=latest_entry,
            reverses_entry=None,
            reason=reason,
            created_by=actor,
        )
    )
    _record_ledger_event(
        action=f"wallet.{entry_type}",
        entry=entry,
        actor=actor,
        request=request,
        reason=reason,
    )
    return entry


@transaction.atomic
def reverse_ledger_entry(
    *,
    entry: LedgerEntry,
    operation_id,
    reason: str,
    actor,
    request: HttpRequest | None = None,
) -> LedgerEntry:
    _require_permission(
        actor,
        "subscribers.view_subscriber",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
    )
    reason = _validate_ledger_reason(reason)
    operation_uuid = _normalize_operation_id(operation_id)
    target_lookup = LedgerEntry.objects.select_related("wallet").get(pk=entry.pk)
    reversal_direction = _opposite_direction(target_lookup.direction)

    existing = _existing_reversal_operation_result(
        target=target_lookup,
        operation_id=operation_uuid,
        direction=reversal_direction,
        reason=reason,
    )
    if existing is not None:
        return existing

    locked_subscriber = _lock_subscriber(target_lookup.wallet.subscriber)
    wallet = _lock_wallet(target_lookup.wallet)
    wallet.subscriber = locked_subscriber
    latest_entry = _lock_latest_ledger_entry(wallet)
    locked_target = (
        LedgerEntry.objects.select_for_update(of=("self",))
        .select_related("wallet")
        .get(pk=entry.pk)
    )
    if locked_target.wallet_id != wallet.pk:
        raise ValidationError("Ledger entry no longer belongs to this wallet.")
    reversal_direction = _opposite_direction(locked_target.direction)

    existing = _existing_reversal_operation_result(
        target=locked_target,
        operation_id=operation_uuid,
        direction=reversal_direction,
        reason=reason,
    )
    if existing is not None:
        return existing
    if locked_target.entry_type == LedgerEntry.ENTRY_REVERSAL:
        raise ValidationError("A reversal cannot reverse another reversal.")
    if locked_target.entry_type not in {
        LedgerEntry.ENTRY_MANUAL_CREDIT,
        LedgerEntry.ENTRY_MANUAL_DEBIT,
    }:
        raise ValidationError("Only manual ledger entries can be reversed.")
    if LedgerEntry.objects.filter(reverses_entry=locked_target).exists():
        raise ValidationError("This ledger entry has already been reversed.")

    current_balance = _ledger_current_balance(latest_entry)
    balance_after = _ledger_resulting_balance(
        current_balance=current_balance,
        direction=reversal_direction,
        amount_minor=locked_target.amount_minor,
    )
    reversal = _save_ledger_entry(
        LedgerEntry(
            wallet=wallet,
            sequence_number=_ledger_next_sequence(latest_entry),
            operation_id=operation_uuid,
            entry_type=LedgerEntry.ENTRY_REVERSAL,
            direction=reversal_direction,
            amount_minor=locked_target.amount_minor,
            balance_after_minor=balance_after,
            previous_entry=latest_entry,
            reverses_entry=locked_target,
            reason=reason,
            created_by=actor,
        )
    )
    _record_ledger_event(
        action="wallet.entry_reversed",
        entry=reversal,
        actor=actor,
        request=request,
        reason=reason,
    )
    return reversal
