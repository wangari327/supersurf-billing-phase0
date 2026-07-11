from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import NoReverseMatch, reverse

from audit.logging import SecretRedactionFilter
from audit.models import AuditEvent
from audit.service import record_event
from core.models import Organization
from core.services import get_or_create_default_organization
from users.models import User
from users.roles import ROLE_ADMINISTRATOR, ROLE_FINANCE, ROLE_OWNER, ROLE_READ_ONLY
from users.services import create_owner_user


def filtered_message(message, args=()):
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record)
    return record.getMessage()


def test_redacts_password_containing_letter_s():
    message = filtered_message("login password=sassy success")
    assert "sassy" not in message
    assert "password=[redacted]" in message
    assert "success" in message


def test_redacts_two_secrets_in_one_message():
    message = filtered_message("secret=first token=second completed")
    assert "first" not in message
    assert "second" not in message
    assert "secret=[redacted]" in message
    assert "token=[redacted]" in message
    assert "completed" in message


def test_redacts_one_secret_followed_by_ordinary_text():
    message = filtered_message("credential=abc123 ordinary text remains")
    assert "abc123" not in message
    assert "credential=[redacted]" in message
    assert "ordinary text remains" in message


def test_redacts_authorization_bearer_header():
    message = filtered_message("Authorization: Bearer bearer-token-123 accepted")
    assert "bearer-token-123" not in message
    assert "Authorization: Bearer [redacted]" in message
    assert "accepted" in message


def test_redacts_values_separated_by_spaces():
    message = filtered_message("cookie sessionid-123 request continues")
    assert "sessionid-123" not in message
    assert "cookie [redacted]" in message
    assert "request continues" in message


def test_redacts_nested_audit_metadata_in_log_record():
    message = filtered_message({"metadata": {"consumer_secret": "nested-secret", "safe": "ok"}})
    assert "nested-secret" not in message
    assert "consumer_secret" in message
    assert "[redacted]" in message
    assert "safe" in message


def test_redacts_exception_style_messages():
    message = filtered_message("failed while handling %s", (ValueError("token=exception-secret"),))
    assert "exception-secret" not in message
    assert "token=[redacted]" in message
    assert "failed while handling" in message


def create_staff_with_role(username: str, role_name: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=role_name))
    return user


@pytest.mark.django_db
def test_administrator_can_assign_non_owner_roles(client, seeded_roles):
    administrator = create_staff_with_role("administrator", ROLE_ADMINISTRATOR)
    target = create_staff_with_role("target", ROLE_READ_ONLY)
    finance = Group.objects.get(name=ROLE_FINANCE)

    client.force_login(administrator)
    response = client.post(
        reverse("assign_roles", args=[target.pk]),
        {"roles": [finance.pk], "reason": "Finance handover"},
    )

    assert response.status_code == 302
    target.refresh_from_db()
    assert list(target.groups.values_list("name", flat=True)) == [ROLE_FINANCE]
    assert AuditEvent.objects.filter(action="staff.roles.changed", actor=administrator).exists()


@pytest.mark.django_db
def test_administrator_cannot_assign_owner_to_self_with_crafted_post(client, seeded_roles):
    administrator = create_staff_with_role("admin-self", ROLE_ADMINISTRATOR)
    owner = Group.objects.get(name=ROLE_OWNER)
    administrator_group = Group.objects.get(name=ROLE_ADMINISTRATOR)

    client.force_login(administrator)
    response = client.post(
        reverse("assign_roles", args=[administrator.pk]),
        {"roles": [administrator_group.pk, owner.pk], "reason": "crafted escalation"},
    )

    assert response.status_code == 403
    administrator.refresh_from_db()
    assert ROLE_OWNER not in administrator.role_names


@pytest.mark.django_db
def test_administrator_cannot_assign_owner_to_another_user(client, seeded_roles):
    administrator = create_staff_with_role("admin-other", ROLE_ADMINISTRATOR)
    target = create_staff_with_role("readonly-target", ROLE_READ_ONLY)
    owner = Group.objects.get(name=ROLE_OWNER)

    client.force_login(administrator)
    response = client.post(
        reverse("assign_roles", args=[target.pk]),
        {"roles": [owner.pk], "reason": "crafted escalation"},
    )

    assert response.status_code == 403
    target.refresh_from_db()
    assert ROLE_OWNER not in target.role_names


@pytest.mark.django_db
def test_administrator_cannot_modify_existing_owner(client, seeded_roles):
    administrator = create_staff_with_role("admin-owner-target", ROLE_ADMINISTRATOR)
    owner_user = create_staff_with_role("existing-owner", ROLE_OWNER)
    finance = Group.objects.get(name=ROLE_FINANCE)

    client.force_login(administrator)
    response = client.post(
        reverse("assign_roles", args=[owner_user.pk]),
        {"roles": [finance.pk], "reason": "crafted owner modification"},
    )

    assert response.status_code == 403
    owner_user.refresh_from_db()
    assert ROLE_OWNER in owner_user.role_names


@pytest.mark.django_db
def test_final_active_owner_role_cannot_be_removed(client, owner_user):
    administrator = Group.objects.get(name=ROLE_ADMINISTRATOR)

    client.force_login(owner_user)
    response = client.post(
        reverse("assign_roles", args=[owner_user.pk]),
        {"roles": [administrator.pk], "reason": "rotate owner"},
    )

    assert response.status_code == 200
    assert "final active Owner" in response.content.decode()
    owner_user.refresh_from_db()
    assert ROLE_OWNER in owner_user.role_names


@pytest.mark.django_db
def test_owner_can_grant_and_remove_owner_when_another_active_owner_exists(client, owner_user):
    target = create_staff_with_role("new-owner", ROLE_READ_ONLY)
    owner_group = Group.objects.get(name=ROLE_OWNER)
    administrator = Group.objects.get(name=ROLE_ADMINISTRATOR)

    client.force_login(owner_user)
    grant_response = client.post(
        reverse("assign_roles", args=[target.pk]),
        {"roles": [owner_group.pk], "reason": "backup owner"},
    )
    assert grant_response.status_code == 302
    target.refresh_from_db()
    assert ROLE_OWNER in target.role_names

    remove_response = client.post(
        reverse("assign_roles", args=[owner_user.pk]),
        {"roles": [administrator.pk], "reason": "owner rotation complete"},
    )
    assert remove_response.status_code == 302
    owner_user.refresh_from_db()
    assert ROLE_OWNER not in owner_user.role_names


@pytest.mark.django_db
def test_organization_admin_is_read_only(admin_client):
    organization = get_or_create_default_organization()
    response = admin_client.post(
        reverse("admin:core_organization_change", args=[organization.pk]),
        {"trading_name": "Changed Through Admin"},
    )

    assert response.status_code == 403
    organization.refresh_from_db()
    assert organization.trading_name != "Changed Through Admin"


@pytest.mark.django_db
def test_user_admin_cannot_change_owner_role(admin_client, owner_user):
    finance = Group.objects.get(name=ROLE_FINANCE)
    response = admin_client.post(
        reverse("admin:users_user_change", args=[owner_user.pk]),
        {"username": owner_user.username, "groups": [finance.pk]},
    )

    assert response.status_code == 403
    owner_user.refresh_from_db()
    assert ROLE_OWNER in owner_user.role_names
    assert not AuditEvent.objects.filter(action="staff.roles.changed").exists()


@pytest.mark.django_db
def test_group_admin_is_not_registered(admin_client):
    with pytest.raises(NoReverseMatch):
        reverse("admin:auth_group_changelist")


def grant_permissions(user: User, *codenames: str) -> None:
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))


def settings_payload(organization: Organization, **overrides: str) -> dict[str, str]:
    branding = organization.branding
    data = {
        "primary_brand": organization.primary_brand,
        "trading_name": organization.trading_name,
        "product_name": organization.product_name,
        "network_label": organization.network_label,
        "support_label": organization.support_label,
        "portal_label": organization.portal_label,
        "domain": organization.domain,
        "support_email": organization.support_email,
        "billing_email": organization.billing_email,
        "noc_email": organization.noc_email,
        "support_phone": organization.support_phone,
        "primary_ui_colour": branding.primary_ui_colour,
        "secondary_ui_colour": branding.secondary_ui_colour,
        "receipt_heading": branding.receipt_heading,
        "invoice_heading": branding.invoice_heading,
        "receipt_footer": branding.receipt_footer,
        "invoice_footer": branding.invoice_footer,
        "payment_instructions": branding.payment_instructions,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_sensitive_settings_are_not_rendered_without_view_permission(client, seeded_roles):
    organization = get_or_create_default_organization()
    organization.kra_pin = "P051234567A"
    organization.paybill_number = "123456"
    organization.save()
    user = User.objects.create_user(username="settings-user", password="StrongPass123!")
    grant_permissions(user, "change_organization")

    client.force_login(user)
    response = client.get(reverse("organization_settings"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "P051234567A" not in content
    assert "123456" not in content
    assert "kra_pin" not in content
    assert "paybill_number" not in content


@pytest.mark.django_db
def test_sensitive_settings_cannot_be_changed_with_only_organization_permission(
    client, seeded_roles
):
    organization = get_or_create_default_organization()
    organization.kra_pin = "P051234567A"
    organization.save()
    user = User.objects.create_user(username="settings-craft", password="StrongPass123!")
    grant_permissions(user, "change_organization")

    client.force_login(user)
    response = client.post(
        reverse("organization_settings"),
        {
            "primary_brand": organization.primary_brand,
            "trading_name": organization.trading_name,
            "product_name": organization.product_name,
            "network_label": organization.network_label,
            "support_label": organization.support_label,
            "portal_label": organization.portal_label,
            "domain": organization.domain,
            "support_email": organization.support_email,
            "billing_email": organization.billing_email,
            "noc_email": organization.noc_email,
            "support_phone": organization.support_phone,
            "kra_pin": "P059999999Z",
        },
    )

    assert response.status_code == 403
    organization.refresh_from_db()
    assert organization.kra_pin == "P051234567A"


@pytest.mark.django_db
def test_sensitive_settings_change_requires_sensitive_permission(client, owner_user):
    organization = get_or_create_default_organization()
    client.force_login(owner_user)

    response = client.post(
        reverse("organization_settings"),
        settings_payload(
            organization,
            registered_business_name="SuperSurf Limited",
            paybill_number="654321",
            till_number="",
            kra_pin="P051234567A",
            registration_number="REG-123",
            communications_authority_licence="CA-123",
        ),
    )

    assert response.status_code == 302
    organization.refresh_from_db()
    assert organization.kra_pin == "P051234567A"
    event = AuditEvent.objects.get(action="organization.settings.changed")
    assert "kra_pin" in event.safe_metadata["changed_fields"]
    assert "P051234567A" not in str(event.safe_metadata)
    assert "654321" not in str(event.safe_metadata)


@pytest.mark.django_db
def test_audit_event_queryset_and_bulk_mutations_are_rejected(owner_user):
    event = record_event(action="test.mutation", actor=owner_user)

    with pytest.raises(RuntimeError):
        AuditEvent.objects.filter(pk=event.pk).update(action="changed")
    with pytest.raises(RuntimeError):
        AuditEvent.objects.filter(pk=event.pk).delete()

    event.action = "changed"
    with pytest.raises(RuntimeError):
        AuditEvent.objects.bulk_update([event], ["action"])
    with pytest.raises(RuntimeError):
        event.save()
    with pytest.raises(RuntimeError):
        event.delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("weak-owner", "short"),
        ("common-owner", "password"),
        ("numeric-owner", "123456789"),
        ("similar-owner", "similar-owner"),
    ],
)
def test_first_owner_rejects_weak_common_numeric_or_similar_passwords(
    seeded_roles, username, password
):
    with pytest.raises(ValidationError):
        create_owner_user(username=username, email="", password=password)


@pytest.mark.django_db
def test_first_owner_accepts_valid_password(seeded_roles):
    user = create_owner_user(
        username="valid-owner",
        email="",
        password="Correct-Horse-Owner-2026!",
    )
    assert user.pk
    assert ROLE_OWNER in user.role_names


@pytest.mark.django_db
def test_first_owner_command_does_not_print_rejected_password(seeded_roles, monkeypatch):
    monkeypatch.setenv("FIRST_OWNER_PASSWORD", "123456789")
    with pytest.raises(CommandError) as exc_info:
        call_command("create_first_owner", username="cmd-owner", email="")
    assert "123456789" not in str(exc_info.value)


VALID_PRODUCTION_ENV = {
    "SUPERSURF_ENVIRONMENT": "PRODUCTION",
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "prod-check-local-only-9a7bc25f-df43-43bb-b84e-1cf3ee701e6b",
    "DATABASE_URL": "postgres://supersurf:supersurf@localhost:5432/supersurf",
    "DJANGO_ALLOWED_HOSTS": "supersurf.localhost",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://supersurf.localhost",
}


def import_settings_with_env(env_updates: dict[str, str]):
    env = os.environ.copy()
    for key in VALID_PRODUCTION_ENV:
        env.pop(key, None)
    env.update(env_updates)
    env["PYTHONPATH"] = str(Path.cwd())
    return subprocess.run(
        [sys.executable, "-c", "import supersurf.settings"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "missing_setting",
    [
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "DJANGO_DEBUG",
    ],
)
def test_production_settings_fail_when_required_setting_is_missing(missing_setting):
    env = VALID_PRODUCTION_ENV.copy()
    env.pop(missing_setting)

    result = import_settings_with_env(env)

    assert result.returncode != 0
    assert missing_setting in result.stderr


def test_production_settings_reject_debug_true():
    env = VALID_PRODUCTION_ENV | {"DJANGO_DEBUG": "true"}
    result = import_settings_with_env(env)

    assert result.returncode != 0
    assert "DJANGO_DEBUG must be explicitly false" in result.stderr


def test_production_settings_reject_development_secret():
    env = VALID_PRODUCTION_ENV | {"DJANGO_SECRET_KEY": "dev-only-insecure-supersurf-key"}
    result = import_settings_with_env(env)

    assert result.returncode != 0
    assert "development fallback" in result.stderr


def test_production_settings_reject_sqlite_database_url():
    env = VALID_PRODUCTION_ENV | {"DATABASE_URL": "sqlite:///db.sqlite3"}
    result = import_settings_with_env(env)

    assert result.returncode != 0
    assert "PostgreSQL" in result.stderr


def test_production_settings_accept_complete_profile():
    result = import_settings_with_env(VALID_PRODUCTION_ENV)

    assert result.returncode == 0


@pytest.mark.django_db
def test_readyz_does_not_create_missing_seed_records(client):
    Organization.objects.all().delete()

    response = client.get(reverse("readyz"))

    assert response.status_code == 503
    assert response.json()["checks"]["organization_seed"] == "missing"
    assert Organization.objects.count() == 0


@pytest.mark.django_db
@override_settings(BROKER_URL="redis://:secret-broker-password@localhost:6379/0")
def test_system_health_does_not_expose_secret_configuration(client, readonly_user):
    client.force_login(readonly_user)
    response = client.get(reverse("system_health"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "redis://" not in content
    assert "secret-broker-password" not in content
    assert "reachability not checked" in content
