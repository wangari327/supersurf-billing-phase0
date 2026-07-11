from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import NoReverseMatch, reverse

from audit.models import AuditEvent
from billing.forms import PlanForm
from billing.models import Plan
from billing.money import format_ksh, ksh_to_minor_units, minor_units_to_ksh
from users.models import User
from users.roles import (
    ROLE_ADMINISTRATOR,
    ROLE_FINANCE,
    ROLE_NOC,
    ROLE_READ_ONLY,
    ROLE_SUPPORT,
)


def create_staff_with_role(username: str, role_name: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=role_name))
    return user


def package_payload(**overrides: str | int) -> dict[str, str | int]:
    data: dict[str, str | int] = {
        "name": "50 Mbps",
        "download_speed_mbps": 50,
        "price_ksh": "2500",
        "duration_days": 30,
        "grace_period_hours": 24,
        "description": "Operator package",
        "reason": "Catalog setup",
    }
    data.update(overrides)
    return data


def create_package(name: str = "100 Mbps") -> Plan:
    return Plan.objects.create(
        name=name,
        download_speed_mbps=100,
        price_minor=300000,
        duration_days=30,
        grace_period_hours=24,
    )


@pytest.mark.django_db
def test_migrations_create_initial_packages():
    packages = list(Plan.objects.filter(name__in=["5 Mbps", "15 Mbps", "30 Mbps"]))
    assert len(packages) == 3


@pytest.mark.django_db
def test_initial_package_speeds_prices_duration_and_grace():
    expected = {
        "5 Mbps": (5, 50000),
        "15 Mbps": (15, 150000),
        "30 Mbps": (30, 200000),
    }
    for name, (speed, price_minor) in expected.items():
        package = Plan.objects.get(name=name)
        assert package.download_speed_mbps == speed
        assert package.price_minor == price_minor
        assert package.duration_days == 30
        assert package.grace_period_hours == 24
        assert package.is_active is True


@pytest.mark.django_db
def test_plan_defaults_duration_and_grace():
    package = Plan.objects.create(name="Default Package", download_speed_mbps=7, price_minor=70000)
    assert package.duration_days == 30
    assert package.grace_period_hours == 24


@pytest.mark.django_db
def test_package_name_is_unique_case_insensitively():
    Plan.objects.create(name="Case Package", download_speed_mbps=10, price_minor=100000)
    with pytest.raises(ValidationError):
        Plan.objects.create(name="case package", download_speed_mbps=11, price_minor=110000)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field, value",
    [
        ("download_speed_mbps", 0),
        ("price_minor", 0),
        ("duration_days", 0),
        ("grace_period_hours", -1),
    ],
)
def test_plan_numeric_validation(field, value):
    data = {
        "name": f"Invalid {field}",
        "download_speed_mbps": 10,
        "price_minor": 100000,
        "duration_days": 30,
        "grace_period_hours": 24,
    }
    data[field] = value
    with pytest.raises(ValidationError):
        Plan.objects.create(**data)


@pytest.mark.django_db
def test_grace_period_may_be_zero():
    package = Plan.objects.create(
        name="Zero Grace",
        download_speed_mbps=8,
        price_minor=80000,
        grace_period_hours=0,
    )
    assert package.grace_period_hours == 0


def test_ksh_to_minor_unit_conversion():
    assert ksh_to_minor_units(Decimal("500")) == 50000
    assert ksh_to_minor_units(Decimal("1500.50")) == 150050


def test_minor_unit_to_ksh_display():
    assert minor_units_to_ksh(150050) == Decimal("1500.50")
    assert format_ksh(150000) == "KSh 1,500"
    assert format_ksh(150050) == "KSh 1,500.50"


@pytest.mark.django_db
def test_plan_form_rejects_excessive_decimal_places():
    form = PlanForm(data=package_payload(price_ksh="1500.505"))
    assert not form.is_valid()
    assert "price_ksh" in form.errors


@pytest.mark.django_db
def test_package_list_permission(client, seeded_roles):
    viewer = create_staff_with_role("package-viewer", ROLE_READ_ONLY)
    no_role = User.objects.create_user(username="no-package-role", password="StrongPass123!")

    client.force_login(no_role)
    assert client.get(reverse("package_list")).status_code == 403

    client.force_login(viewer)
    response = client.get(reverse("package_list"))
    assert response.status_code == 200
    assert b"5 Mbps" in response.content


@pytest.mark.django_db
def test_package_detail_permission(client, seeded_roles):
    package = Plan.objects.get(name="15 Mbps")
    viewer = create_staff_with_role("package-detail-viewer", ROLE_FINANCE)
    no_role = User.objects.create_user(username="no-detail-role", password="StrongPass123!")

    client.force_login(no_role)
    assert client.get(reverse("package_detail", args=[package.pk])).status_code == 403

    client.force_login(viewer)
    response = client.get(reverse("package_detail", args=[package.pk]))
    assert response.status_code == 200
    assert b"KSh 1,500" in response.content


@pytest.mark.django_db
def test_administrator_can_create_and_edit_package(client, seeded_roles):
    administrator = create_staff_with_role("package-admin", ROLE_ADMINISTRATOR)
    client.force_login(administrator)

    create_response = client.post(reverse("package_create"), package_payload(name="75 Mbps"))
    assert create_response.status_code == 302
    package = Plan.objects.get(name="75 Mbps")
    assert package.price_minor == 250000

    edit_response = client.post(
        reverse("package_edit", args=[package.pk]),
        package_payload(
            name="75 Mbps Plus",
            download_speed_mbps=75,
            price_ksh="2750",
            reason="Catalog price review",
        ),
    )
    assert edit_response.status_code == 302
    package.refresh_from_db()
    assert package.name == "75 Mbps Plus"
    assert package.price_minor == 275000
    assert AuditEvent.objects.filter(action="package.created", actor=administrator).exists()
    assert AuditEvent.objects.filter(action="package.updated", actor=administrator).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("role_name", [ROLE_FINANCE, ROLE_NOC, ROLE_SUPPORT, ROLE_READ_ONLY])
def test_non_admin_roles_cannot_mutate_packages_with_crafted_requests(
    client, seeded_roles, role_name
):
    user = create_staff_with_role(f"crafted-{role_name}".lower().replace(" ", "-"), role_name)
    package = create_package(name=f"Immutable {role_name}")
    client.force_login(user)

    create_response = client.post(reverse("package_create"), package_payload(name="Crafted"))
    assert create_response.status_code == 403
    assert (
        client.post(
            reverse("package_edit", args=[package.pk]),
            package_payload(name="Crafted Edit"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("package_deactivate", args=[package.pk]),
            {"reason": "crafted deactivate"},
        ).status_code
        == 403
    )
    package.refresh_from_db()
    assert package.is_active is True
    assert not AuditEvent.objects.filter(target_identifier=str(package.pk)).exists()


@pytest.mark.django_db
def test_package_deactivation_and_reactivation(client, seeded_roles):
    administrator = create_staff_with_role("status-admin", ROLE_ADMINISTRATOR)
    package = create_package(name="Status Package")
    client.force_login(administrator)

    deactivate_response = client.post(
        reverse("package_deactivate", args=[package.pk]),
        {"reason": "No longer sold"},
    )
    assert deactivate_response.status_code == 302
    package.refresh_from_db()
    assert package.is_active is False

    reactivate_response = client.post(
        reverse("package_reactivate", args=[package.pk]),
        {"reason": "Back in catalog"},
    )
    assert reactivate_response.status_code == 302
    package.refresh_from_db()
    assert package.is_active is True
    assert AuditEvent.objects.filter(action="package.deactivated").exists()
    assert AuditEvent.objects.filter(action="package.reactivated").exists()


@pytest.mark.django_db
def test_status_transitions_are_post_only(client, seeded_roles):
    administrator = create_staff_with_role("post-only-admin", ROLE_ADMINISTRATOR)
    package = create_package(name="POST Only")
    client.force_login(administrator)

    assert client.get(reverse("package_deactivate", args=[package.pk])).status_code == 405
    assert client.get(reverse("package_reactivate", args=[package.pk])).status_code == 405


@pytest.mark.django_db
def test_audit_metadata_is_focused_and_omits_raw_post_payload(client, seeded_roles):
    administrator = create_staff_with_role("audit-package-admin", ROLE_ADMINISTRATOR)
    client.force_login(administrator)
    response = client.post(
        reverse("package_create"),
        package_payload(name="Audit Package", csrfmiddlewaretoken="raw-token"),
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="package.created")
    assert event.reason == "Catalog setup"
    metadata = str(event.safe_metadata)
    assert "raw-token" not in metadata
    assert "csrfmiddlewaretoken" not in metadata
    assert "reason" not in event.safe_metadata
    assert event.safe_metadata["new"]["name"] == "Audit Package"


@pytest.mark.django_db
def test_django_admin_cannot_mutate_package(admin_client):
    package = create_package(name="Admin Protected")
    response = admin_client.post(
        reverse("admin:billing_plan_change", args=[package.pk]),
        {"name": "Admin Changed", "download_speed_mbps": 1, "price_minor": 1},
    )

    assert response.status_code == 403
    package.refresh_from_db()
    assert package.name == "Admin Protected"


def test_no_package_delete_route():
    with pytest.raises(NoReverseMatch):
        reverse("package_delete", args=["00000000-0000-0000-0000-000000000000"])


def test_no_upload_speed_field_exists():
    assert "upload_speed_mbps" not in {field.name for field in Plan._meta.fields}


@pytest.mark.django_db
def test_role_seeding_remains_idempotent(seeded_roles):
    call_command("seed_roles", verbosity=0)
    call_command("seed_roles", verbosity=0)
    administrator_permissions = set(
        Group.objects.get(name=ROLE_ADMINISTRATOR)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    assert ("billing", "view_plan") in administrator_permissions
    assert ("billing", "add_plan") in administrator_permissions
    assert ("billing", "change_plan") in administrator_permissions
    assert ("billing", "delete_plan") not in administrator_permissions
