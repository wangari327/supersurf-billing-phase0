from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render

from audit.service import record_event
from billing.models import Plan
from subscribers.models import Service, Subscriber

from .forms import BrandingForm, OrganizationForm, SensitiveOrganizationForm
from .services import (
    default_organization_seeded,
    get_or_create_default_organization,
    production_readiness_issues,
)

SENSITIVE_ORGANIZATION_FIELDS = set(SensitiveOrganizationForm.Meta.fields)


@login_required
def dashboard(request):
    organization = get_or_create_default_organization()
    issues = production_readiness_issues(organization)
    can_view_packages = request.user.has_perm("billing.view_plan")
    can_view_subscribers = request.user.has_perm("subscribers.view_subscriber")
    package_summary = None
    subscriber_summary = None
    if can_view_packages:
        package_summary = {
            "active_count": Plan.objects.filter(is_active=True).count(),
            "inactive_count": Plan.objects.filter(is_active=False).count(),
        }
    if can_view_subscribers:
        subscriber_summary = {
            "active_subscribers": Subscriber.objects.filter(is_active=True).count(),
            "inactive_subscribers": Subscriber.objects.filter(is_active=False).count(),
            "active_services": Service.objects.filter(is_active=True).count(),
            "inactive_services": Service.objects.filter(is_active=False).count(),
        }
    return render(
        request,
        "core/dashboard.html",
        {
            "organization": organization,
            "issues": issues,
            "coming_later": [
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
            "package_summary": package_summary,
            "subscriber_summary": subscriber_summary,
        },
    )


@login_required
@permission_required("core.change_organization", raise_exception=True)
def organization_settings(request):
    organization = get_or_create_default_organization()
    branding = organization.branding
    can_view_sensitive = request.user.has_perm("core.view_sensitive_settings")
    can_change_sensitive = request.user.has_perm("core.change_sensitive_settings")
    if request.method == "POST":
        if SENSITIVE_ORGANIZATION_FIELDS.intersection(request.POST) and not can_change_sensitive:
            raise PermissionDenied("Changing sensitive settings requires explicit permission.")
        organization_form = OrganizationForm(request.POST, instance=organization)
        branding_form = BrandingForm(request.POST, instance=branding)
        sensitive_form = (
            SensitiveOrganizationForm(
                request.POST,
                instance=organization,
                can_change=can_change_sensitive,
            )
            if can_change_sensitive
            else None
        )
        sensitive_valid = sensitive_form is None or sensitive_form.is_valid()
        if organization_form.is_valid() and branding_form.is_valid() and sensitive_valid:
            sensitive_changed_fields = sensitive_form.changed_data if sensitive_form else []
            changed_fields = list(
                organization_form.changed_data
                + branding_form.changed_data
                + sensitive_changed_fields
            )
            with transaction.atomic():
                organization_form.save()
                branding_form.save()
                if sensitive_form:
                    sensitive_form.save()
            record_event(
                action="organization.settings.changed",
                request=request,
                target_type="organization",
                target_identifier=organization.pk,
                metadata={"changed_fields": changed_fields},
            )
            messages.success(request, "SuperSurf settings updated.")
            return redirect("organization_settings")
        visible_sensitive_form = sensitive_form if can_view_sensitive else None
    else:
        organization_form = OrganizationForm(instance=organization)
        branding_form = BrandingForm(instance=branding)
        visible_sensitive_form = (
            SensitiveOrganizationForm(instance=organization, can_change=can_change_sensitive)
            if can_view_sensitive
            else None
        )

    return render(
        request,
        "core/settings.html",
        {
            "organization": organization,
            "organization_form": organization_form,
            "branding_form": branding_form,
            "sensitive_form": visible_sensitive_form,
            "can_change_sensitive_settings": can_change_sensitive,
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
        checks["organization_seed"] = "ok" if default_organization_seeded() else "missing"
        if checks["organization_seed"] != "ok":
            status_code = 503
    except Exception:
        checks["organization_seed"] = "error"
        status_code = 503

    return JsonResponse(
        {"status": "ok" if status_code == 200 else "error", "checks": checks},
        status=status_code,
    )


@login_required
def system_health(request):
    organization = get_or_create_default_organization()
    broker_status = (
        "configured; reachability not checked here" if settings.BROKER_URL else "not configured"
    )
    return render(
        request,
        "core/system_health.html",
        {
            "organization": organization,
            "database_engine": connection.vendor,
            "broker_status": broker_status,
            "issues": production_readiness_issues(organization),
        },
    )
