from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction

from audit.service import record_event

from .models import MpesaCallbackEvent

MAX_CALLBACK_BODY_BYTES = 64 * 1024
MAX_CALLBACK_AMOUNT = Decimal("9999999999.99")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "phone",
    "msisdn",
    "first_name",
    "firstname",
    "middle_name",
    "middlename",
    "last_name",
    "lastname",
    "full_name",
    "account_balance",
    "orgaccountbalance",
    "credential",
    "password",
    "passkey",
    "secret",
    "token",
    "authorization",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapturedCallback:
    event: MpesaCallbackEvent
    created: bool
    conflicting_duplicate: bool = False


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sanitize_payload(value: Any, *, key_name: str = "") -> Any:
    if _is_sensitive_key(key_name):
        return REDACTED
    if isinstance(value, dict):
        sensitive_item_name = _metadata_item_name(value)
        return {
            str(child_key): (
                REDACTED
                if child_key == "Value" and sensitive_item_name is not None
                else sanitize_payload(child_value, key_name=str(child_key))
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_payload(item, key_name=key_name) for item in value]
    return value


def capture_mpesa_callback(event_type: str, payload: Any) -> CapturedCallback:
    digest = payload_digest(payload)
    sanitized = sanitize_payload(payload)
    extracted = _extract_callback_fields(payload)
    idempotency_key = _idempotency_key(event_type, extracted, digest)
    event_data = {
        "event_type": event_type,
        "payload_sha256": digest,
        "idempotency_key": idempotency_key,
        "sanitized_payload": sanitized,
        **extracted,
    }
    try:
        with transaction.atomic():
            event = MpesaCallbackEvent.objects.create(**event_data)
            created = True
    except IntegrityError:
        event = MpesaCallbackEvent.objects.get(idempotency_key=idempotency_key)
        created = False
    conflicting_duplicate = not created and event.payload_sha256 != digest
    status = "conflict" if conflicting_duplicate else "new" if created else "duplicate"
    log_method = logger.warning if conflicting_duplicate else logger.info
    log_method(
        "mpesa_callback_event id=%s event_type=%s status=%s",
        event.pk,
        event.event_type,
        status,
    )
    if conflicting_duplicate:
        record_event(
            action="mpesa.callback_conflict",
            target_type="mpesa_callback_event",
            target_identifier=event.pk,
            metadata={"outcome": "duplicate_payload_conflict"},
            result="skipped",
            reason="duplicate_payload_conflict",
        )
    return CapturedCallback(
        event=event,
        created=created,
        conflicting_duplicate=conflicting_duplicate,
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _metadata_item_name(value: dict[Any, Any]) -> str | None:
    name = value.get("Name")
    if isinstance(name, str) and _is_sensitive_key(name):
        return name
    return None


def _extract_callback_fields(payload: Any) -> dict[str, Any]:
    provider_external_identifier = _normalize_provider_identifier(
        _first_value(payload, "BusinessShortCode")
    )
    provider_transaction_id = _normalize_text(
        _coalesce(_first_value(payload, "TransID"), _metadata_value(payload, "MpesaReceiptNumber")),
        max_length=128,
    )
    merchant_request_id = _normalize_text(
        _first_value(payload, "MerchantRequestID"),
        max_length=128,
    )
    checkout_request_id = _normalize_text(
        _first_value(payload, "CheckoutRequestID"),
        max_length=128,
    )
    account_reference = _normalize_text(
        _coalesce(
            _first_value(payload, "BillRefNumber"),
            _first_value(payload, "AccountReference"),
        ),
        max_length=64,
    )
    amount = _normalize_decimal(
        _coalesce(_first_value(payload, "TransAmount"), _metadata_value(payload, "Amount"))
    )
    result_code = _normalize_text(
        _coalesce(_first_value(payload, "ResultCode"), _first_value(payload, "ResponseCode")),
        max_length=16,
    )
    result_description = _normalize_text(
        _coalesce(
            _first_value(payload, "ResultDesc"),
            _first_value(payload, "ResultDescription"),
        ),
        max_length=240,
        truncate=True,
    )
    return {
        "provider_external_identifier": provider_external_identifier,
        "provider_transaction_id": provider_transaction_id,
        "merchant_request_id": merchant_request_id,
        "checkout_request_id": checkout_request_id,
        "account_reference": account_reference,
        "amount": amount,
        "result_code": result_code,
        "result_description": result_description,
    }


def _normalize_provider_identifier(value: Any) -> str | None:
    text = _normalize_text(value, max_length=64)
    if text is None or not text.isascii() or not text.isdigit() or not 5 <= len(text) <= 12:
        return None
    return text


def _idempotency_key(event_type: str, extracted: dict[str, Any], digest: str) -> str:
    stable_value = None
    if event_type in {
        MpesaCallbackEvent.EVENT_C2B_VALIDATION,
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
    }:
        stable_value = extracted["provider_transaction_id"]
    elif event_type == MpesaCallbackEvent.EVENT_STK_RESULT:
        stable_value = extracted["checkout_request_id"]
    if stable_value:
        return f"{event_type}:{stable_value}"
    return f"{event_type}:sha256:{digest}"


def _first_value(value: Any, *keys: str) -> Any:
    wanted = {key.lower() for key in keys}
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if str(child_key).lower() in wanted:
                return child_value
        for child_value in value.values():
            found = _first_value(child_value, *keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _first_value(item, *keys)
            if found is not None:
                return found
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _metadata_value(value: Any, *names: str) -> Any:
    wanted = {name.lower() for name in names}
    if isinstance(value, dict):
        if "Name" in value and "Value" in value and str(value["Name"]).lower() in wanted:
            return value["Value"]
        for child_value in value.values():
            found = _metadata_value(child_value, *names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _metadata_value(item, *names)
            if found is not None:
                return found
    return None


def _normalize_text(
    value: Any,
    *,
    max_length: int | None = None,
    truncate: bool = False,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None and len(text) > max_length:
        return text[:max_length] if truncate else None
    return text


def _normalize_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        amount = Decimal(text)
        if not amount.is_finite() or amount <= 0:
            return None
        normalized = amount.quantize(Decimal("0.01"))
        if amount != normalized:
            return None
        amount = normalized
    except InvalidOperation:
        return None
    if amount > MAX_CALLBACK_AMOUNT:
        return None
    return amount
