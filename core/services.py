from __future__ import annotations

from django.conf import settings

from .defaults import SUPERSURF_DEFAULTS, ReadinessIssue
from .models import Organization, OrganizationBranding


def get_or_create_default_organization() -> Organization:
    organization, _ = Organization.objects.get_or_create(
        pk=1,
        defaults=SUPERSURF_DEFAULTS,
    )
    OrganizationBranding.objects.get_or_create(organization=organization)
    return organization


def default_organization_seeded() -> bool:
    return Organization.objects.filter(pk=1).exists() and OrganizationBranding.objects.filter(
        organization_id=1
    ).exists()


def production_readiness_issues(organization: Organization) -> list[ReadinessIssue]:
    issues: list[ReadinessIssue] = []
    if settings.SUPERSURF_ENVIRONMENT == "PRODUCTION":
        required_fields = {
            "domain": "Public domain is not configured.",
            "support_email": "Support email is not configured.",
            "billing_email": "Billing email is not configured.",
            "noc_email": "NOC email is not configured.",
        }
        for field_name, message in required_fields.items():
            if not getattr(organization, field_name):
                issues.append(ReadinessIssue(code=f"missing_{field_name}", message=message))

    if settings.SECRET_KEY == "dev-only-insecure-supersurf-key":
        issues.append(
            ReadinessIssue(
                code="development_secret_key",
                message="Django secret key is using the local development fallback.",
                severity="error" if settings.SUPERSURF_ENVIRONMENT == "PRODUCTION" else "warning",
            )
        )
    return issues


def environment_badge_colour() -> str:
    return {
        "DEVELOPMENT": "bg-sky-50 text-sky-800 ring-sky-700/20",
        "TEST": "bg-violet-50 text-violet-800 ring-violet-700/20",
        "LAB": "bg-amber-50 text-amber-900 ring-amber-700/20",
        "PRODUCTION": "bg-rose-50 text-rose-800 ring-rose-700/20",
    }.get(settings.SUPERSURF_ENVIRONMENT, "bg-slate-50 text-slate-800 ring-slate-700/20")
