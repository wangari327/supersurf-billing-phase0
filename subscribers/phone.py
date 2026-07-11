from __future__ import annotations

from django.core.exceptions import ValidationError


def normalize_kenyan_phone(value: str) -> str:
    normalized = "".join(char for char in value.strip() if char not in " -()")
    if not normalized:
        raise ValidationError("Primary phone is required.")

    if normalized.startswith("+254"):
        national = normalized[4:]
    elif normalized.startswith("254"):
        national = normalized[3:]
    elif normalized.startswith("0"):
        national = normalized[1:]
    else:
        raise ValidationError("Enter a Kenya phone number starting with +254, 254, or 0.")

    if len(national) != 9 or not national.isdigit() or national[0] not in {"1", "7"}:
        raise ValidationError("Enter a valid Kenya mobile or fixed wireless number.")
    return f"+254{national}"
