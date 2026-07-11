from __future__ import annotations

from dataclasses import dataclass

KENYA_DEFAULTS = {
    "country": "Kenya",
    "country_code": "KE",
    "currency": "KES",
    "currency_display_label": "KSh",
    "timezone": "Africa/Nairobi",
    "locale": "en-KE",
    "date_format": "DD/MM/YYYY",
    "time_format": "24-hour",
    "week_start": "Monday",
    "telephone_country_code": "+254",
}

SUPERSURF_DEFAULTS = {
    "primary_brand": "SuperSurf",
    "trading_name": "SuperSurf",
    "product_name": "SuperSurf Billing",
    "network_label": "SuperSurf Networks",
    "support_label": "SuperSurf Support",
    "portal_label": "SuperSurf Portal",
    **KENYA_DEFAULTS,
}


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    severity: str = "warning"

