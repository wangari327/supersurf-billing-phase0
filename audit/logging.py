from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEY_PARTS = (
    "secret",
    "password",
    "token",
    "credential",
    "authorization",
    "cookie",
    "consumer_key",
    "consumer-key",
    "consumer_secret",
    "consumer-secret",
    "key",
)

SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"""
    \b
    (?P<key>
        secret
        | password
        | token
        | credential
        | authorization
        | cookie
        | consumer[_-]?key
        | consumer[_-]?secret
        | key
    )
    \b
    (?P<separator>\s*(?:=|:)\s*|\s+)
    (?P<scheme>Bearer\s+)?
    (?P<value>
        (?!%(?:\([^)]+\))?[#0+\- 0-9.]*[a-zA-Z])
        [^\s,;]+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

MPESA_CALLBACK_PATH_PATTERN = re.compile(
    r"(?P<prefix>/api/integrations/mpesa/)[^/\s?#]+"
    r"(?P<suffix>/(?:c2b/(?:validation|confirmation)|stk/callback)/?)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part.replace("-", "_") in lowered for part in SENSITIVE_KEY_PARTS)


def redact_text(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        scheme = match.group("scheme") or ""
        return f"{match.group('key')}{match.group('separator')}{scheme}[redacted]"

    value = MPESA_CALLBACK_PATH_PATTERN.sub(
        r"\g<prefix>[redacted]\g<suffix>",
        value,
    )
    return SENSITIVE_ASSIGNMENT_PATTERN.sub(replace, value)


def redact_log_value(value: Any, *, key: str = "") -> Any:
    if key and is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, BaseException):
        return redact_text(str(value))
    if isinstance(value, Mapping):
        return {
            item_key: redact_log_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_log_value(item) for item in value)
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    return value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_value(record.msg)
        record.args = redact_log_value(record.args)
        return True
