from __future__ import annotations

import logging

import pytest
from django.test import override_settings
from django.urls import reverse

from audit.logging import SecretRedactionFilter
from core.models import Organization
from core.services import get_or_create_default_organization, production_readiness_issues
from users.models import User


@pytest.mark.django_db
def test_supersurf_seed_defaults():
    organization = get_or_create_default_organization()
    assert organization.primary_brand == "SuperSurf"
    assert organization.product_name == "SuperSurf Billing"
    assert organization.network_label == "SuperSurf Networks"
    assert organization.support_label == "SuperSurf Support"
    assert organization.portal_label == "SuperSurf Portal"


@pytest.mark.django_db
def test_kenya_defaults():
    organization = get_or_create_default_organization()
    assert organization.country == "Kenya"
    assert organization.country_code == "KE"
    assert organization.currency == "KES"
    assert organization.currency_display_label == "KSh"
    assert organization.timezone == "Africa/Nairobi"
    assert organization.locale == "en-KE"
    assert organization.telephone_country_code == "+254"


@pytest.mark.django_db
def test_no_invented_domain_or_email_values():
    organization = get_or_create_default_organization()
    assert organization.domain == ""
    assert organization.support_email == ""
    assert organization.billing_email == ""
    assert organization.noc_email == ""
    assert organization.paybill_number == ""
    assert organization.till_number == ""


@pytest.mark.django_db
def test_custom_user_model():
    user = User.objects.create_user(username="staff", password="StrongPass123!")
    assert user.pk
    assert user.role_names == []


@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_readiness_endpoint(client):
    response = client.get(reverse("readyz"))
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


@pytest.mark.django_db
@override_settings(SUPERSURF_ENVIRONMENT="PRODUCTION", SECRET_KEY="production-test-key")
def test_missing_production_settings_are_reported():
    organization = Organization.objects.create()
    issues = production_readiness_issues(organization)
    codes = {issue.code for issue in issues}
    assert "missing_domain" in codes
    assert "missing_support_email" in codes
    assert "missing_billing_email" in codes
    assert "missing_noc_email" in codes


def test_log_secret_redaction():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="password=hunter2 token=abc123",
        args=(),
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record)
    assert "hunter2" not in record.getMessage()
    assert "abc123" not in record.getMessage()
    assert "[redacted]" in record.getMessage()


@pytest.mark.django_db
def test_dashboard_access(client, readonly_user):
    client.force_login(readonly_user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"SuperSurf Billing" in response.content

