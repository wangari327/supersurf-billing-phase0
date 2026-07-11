from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from audit.service import record_event

from .forms import BrandingForm, OrganizationForm
from .services import get_or_create_default_organization, production_readiness_issues


@login_required
def dashboard(request):
    organization = get_or_create_default_organization()
    issues = production_readiness_issues(organization)
    return render(
        request,
        "core/dashboard.html",
        {
            "organization": organization,
            "issues": issues,
            "coming_later": [
                "Subscribers",
                "Plans",
                "Payments",
                "Unmatched Payments",
                "Invoices",
                "Wallet and Ledger",
                "Sessions",
                "Routers and NAS",
                "Provisioning Jobs",
                "Reports",
                "Reconciliation",
                "SuperSurf Support",
            ],
        },
    )


@login_required
@permission_required("core.change_organization", raise_exception=True)
def organization_settings(request):
    organization = get_or_create_default_organization()
    branding = organization.branding
    if request.method == "POST":
        organization_form = OrganizationForm(request.POST, instance=organization)
        branding_form = BrandingForm(request.POST, instance=branding)
        if organization_form.is_valid() and branding_form.is_valid():
            changed_fields = list(organization_form.changed_data + branding_form.changed_data)
            organization_form.save()
            branding_form.save()
            record_event(
                action="organization.settings.changed",
                request=request,
                target_type="organization",
                target_identifier=organization.pk,
                metadata={"changed_fields": changed_fields},
            )
            messages.success(request, "SuperSurf settings updated.")
            return redirect("organization_settings")
    else:
        organization_form = OrganizationForm(instance=organization)
        branding_form = BrandingForm(instance=branding)

    return render(
        request,
        "core/settings.html",
        {
            "organization": organization,
            "organization_form": organization_form,
            "branding_form": branding_form,
            "issues": production_readiness_issues(organization),
        },
    )


def healthz(request):
    return JsonResponse({"status": "ok", "service": "SuperSurf Billing"})


def readyz(request):
    checks: dict[str, str] = {}
    status_code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        status_code = 503

    try:
        organization = get_or_create_default_organization()
        checks["organization"] = "ok" if organization.pk else "error"
    except Exception:
        checks["organization"] = "error"
        status_code = 503

    return JsonResponse(
        {"status": "ok" if status_code == 200 else "error", "checks": checks},
        status=status_code,
    )


@login_required
def system_health(request):
    organization = get_or_create_default_organization()
    broker_status = "configured" if settings.BROKER_URL else "not configured"
    return render(
        request,
        "core/system_health.html",
        {
            "organization": organization,
            "database_engine": connection.vendor,
            "broker_url": settings.BROKER_URL,
            "broker_status": broker_status,
            "issues": production_readiness_issues(organization),
        },
    )
