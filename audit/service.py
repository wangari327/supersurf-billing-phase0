from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.http import HttpRequest

from .models import AuditEvent

SENSITIVE_KEY_PARTS = (
    "secret",
    "password",
    "token",
    "key",
    "credential",
    "consumer",
    "passphrase",
    "cookie",
    "authorization",
    "pin",
    "kra",
)


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


def safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {str(key): redact_value(str(key), value) for key, value in metadata.items()}


def client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_event(
    *,
    action: str,
    actor=None,
    request: HttpRequest | None = None,
    target_type: str = "",
    target_identifier: str = "",
    metadata: Mapping[str, Any] | None = None,
    result: str = "success",
    reason: str = "",
) -> AuditEvent:
    if actor is None and request is not None and getattr(request, "user", None) is not None:
        actor = request.user if request.user.is_authenticated else None
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_identifier=str(target_identifier),
        correlation_id=getattr(request, "correlation_id", "") if request else "",
        safe_metadata=safe_metadata(metadata),
        source_ip=client_ip(request),
        result=result,
        reason=reason,
    )
