from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

KES_QUANTUM = Decimal("0.01")


def ksh_to_minor_units(value: Decimal | str) -> int:
    try:
        amount = Decimal(str(value)).quantize(KES_QUANTUM)
    except InvalidOperation as exc:
        raise ValidationError("Enter a valid KSh amount.") from exc

    if amount <= 0:
        raise ValidationError("Price must be greater than zero.")
    if Decimal(str(value)) != amount:
        raise ValidationError("Price may have at most two decimal places.")
    return int(amount * 100)


def minor_units_to_ksh(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(KES_QUANTUM)


def format_ksh(value: int) -> str:
    amount = minor_units_to_ksh(value)
    if amount == amount.to_integral_value():
        return f"KSh {int(amount):,}"
    return f"KSh {amount:,.2f}"
