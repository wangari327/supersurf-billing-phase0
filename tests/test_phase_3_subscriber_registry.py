from __future__ import annotations

import pytest
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.urls import NoReverseMatch, reverse

from audit.models import AuditEvent
from subscribers.forms import ServiceForm, SubscriberForm
from subscribers.models import Service, Subscriber, SubscriberSequence
from subscribers.phone import normalize_kenyan_phone
from subscribers.services import (
    create_service,
    create_subscriber,
    set_service_active,
    set_subscriber_active,
)
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


def subscriber_payload(**overrides: str) -> dict[str, str]:
    data = {
        "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
        "display_name": "Wangari Home",
        "primary_phone": "0712 345 678",
        "email": "wangari@example.test",
        "reason": "Subscriber registry setup",
    }
    data.update(overrides)
    return data


def service_payload(**overrides: str) -> dict[str, str]:
    data = {"label": "Home fibre", "reason": "Service registry setup"}
    data.update(overrides)
    return data


def valid_subscriber_form(**overrides: str) -> SubscriberForm:
    form = SubscriberForm(data=subscriber_payload(**overrides))
    assert form.is_valid(), form.errors
    return form


def valid_service_form(**overrides: str) -> ServiceForm:
    form = ServiceForm(data=service_payload(**overrides))
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(**overrides: str) -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(**overrides), actor=None)


def create_test_service(subscriber: Subscriber, **overrides: str) -> Service:
    return create_service(subscriber=subscriber, form=valid_service_form(**overrides), actor=None)


@pytest.mark.django_db
def test_account_sequence_is_seeded_by_migration():
    sequence = SubscriberSequence.objects.get(key="subscriber_account")
    assert sequence.next_value == 1


@pytest.mark.django_db
def test_generated_subscriber_and_service_identifiers_start_at_expected_values():
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)

    assert subscriber.account_number == "SS000001"
    assert service.service_number == 1
    assert service.service_reference == "SS000001-01"
    assert service.subscriber == subscriber


@pytest.mark.django_db
def test_allocator_advances_past_unexpected_account_collision():
    Subscriber.objects.create(
        account_number="SS000001",
        customer_type=Subscriber.CUSTOMER_INDIVIDUAL,
        display_name="Existing Customer",
        primary_phone="0711111111",
    )

    subscriber = create_test_subscriber(primary_phone="0712222222")

    assert subscriber.account_number == "SS000002"


@pytest.mark.django_db
def test_service_allocator_advances_past_unexpected_reference_collision():
    subscriber = create_test_subscriber()
    Service.objects.create(
        subscriber=subscriber,
        service_number=1,
        service_reference="SS000001-01",
        label="Existing service",
    )

    service = create_test_service(subscriber, label="Second service")

    assert service.service_number == 2
    assert service.service_reference == "SS000001-02"


@pytest.mark.django_db
def test_hundredth_service_is_rejected():
    subscriber = create_test_subscriber()
    for index in range(99):
        create_test_service(subscriber, label=f"Service {index + 1}")

    with pytest.raises(ValidationError, match="at most 99 services"):
        create_test_service(subscriber, label="Service 100")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0712345678", "+254712345678"),
        ("0112345678", "+254112345678"),
        ("254712345678", "+254712345678"),
        ("+254712345678", "+254712345678"),
        ("0712-345-678", "+254712345678"),
        ("(0712) 345 678", "+254712345678"),
    ],
)
def test_kenya_phone_normalization(raw, expected):
    assert normalize_kenyan_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "712345678", "+255712345678", "0201234567"])
def test_kenya_phone_normalization_rejects_invalid_values(raw):
    with pytest.raises(ValidationError):
        normalize_kenyan_phone(raw)


def test_identifier_fields_are_not_form_fields():
    assert "account_number" not in SubscriberForm().fields
    assert "subscriber" not in ServiceForm().fields
    assert "service_number" not in ServiceForm().fields
    assert "service_reference" not in ServiceForm().fields


@pytest.mark.django_db
def test_subscriber_account_number_is_immutable_through_save_update_and_bulk_update():
    subscriber = create_test_subscriber()

    subscriber.account_number = "SS999999"
    with pytest.raises(RuntimeError):
        subscriber.save()

    with pytest.raises(RuntimeError):
        Subscriber.objects.filter(pk=subscriber.pk).update(account_number="SS999999")

    subscriber = Subscriber.objects.get(pk=subscriber.pk)
    subscriber.account_number = "SS999999"
    with pytest.raises(RuntimeError):
        Subscriber.objects.bulk_update([subscriber], ["account_number"])

    assert Subscriber.objects.get(pk=subscriber.pk).account_number == "SS000001"


@pytest.mark.django_db
def test_service_identifiers_are_immutable_through_save_update_and_bulk_update():
    subscriber = create_test_subscriber()
    other_subscriber = create_test_subscriber(primary_phone="0713333333")
    service = create_test_service(subscriber)

    service.subscriber = other_subscriber
    with pytest.raises(RuntimeError):
        service.save()

    with pytest.raises(RuntimeError):
        Service.objects.filter(pk=service.pk).update(service_reference="SS000001-02")

    service = Service.objects.get(pk=service.pk)
    service.service_number = 2
    with pytest.raises(RuntimeError):
        Service.objects.bulk_update([service], ["service_number"])

    service = Service.objects.get(pk=service.pk)
    assert service.subscriber == subscriber
    assert service.service_number == 1
    assert service.service_reference == "SS000001-01"


@pytest.mark.django_db
def test_service_protects_subscriber_from_orm_delete():
    subscriber = create_test_subscriber()
    create_test_service(subscriber)

    with pytest.raises(ProtectedError):
        subscriber.delete()


@pytest.mark.django_db
def test_status_changes_are_audited_and_repeated_changes_are_rejected():
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)

    set_subscriber_active(
        subscriber=subscriber,
        is_active=False,
        reason="Paused account",
        actor=None,
    )
    service.refresh_from_db()
    assert service.is_active is True

    with pytest.raises(ValidationError, match="already inactive"):
        set_subscriber_active(
            subscriber=subscriber,
            is_active=False,
            reason="Duplicate pause",
            actor=None,
        )

    set_service_active(service=service, is_active=False, reason="Service pause", actor=None)
    with pytest.raises(ValidationError, match="already inactive"):
        set_service_active(service=service, is_active=False, reason="Duplicate pause", actor=None)

    assert AuditEvent.objects.filter(action="subscriber.deactivated").count() == 1
    assert AuditEvent.objects.filter(action="service.deactivated").count() == 1


@pytest.mark.django_db
def test_subscriber_list_permission_search_and_pagination(client, seeded_roles):
    viewer = create_staff_with_role("subscriber-viewer", ROLE_READ_ONLY)
    no_role = User.objects.create_user(username="no-subscriber-role", password="StrongPass123!")
    subscriber = create_test_subscriber(display_name="Searchable Customer")
    service = create_test_service(subscriber, label="Searchable service")

    client.force_login(no_role)
    assert client.get(reverse("subscriber_list")).status_code == 403

    client.force_login(viewer)
    response = client.get(reverse("subscriber_list"), {"q": service.service_reference})
    assert response.status_code == 200
    assert subscriber.account_number.encode() in response.content

    for index in range(20):
        create_test_subscriber(
            display_name=f"Pagination {index}",
            primary_phone=f"0713{index:06d}",
        )
    response = client.get(reverse("subscriber_list"), {"status": "active"})
    assert response.status_code == 200
    assert "status=active&page=2" in response.content.decode()


@pytest.mark.django_db
def test_administrator_can_create_edit_and_status_subscriber_and_service(client, seeded_roles):
    administrator = create_staff_with_role("subscriber-admin", ROLE_ADMINISTRATOR)
    client.force_login(administrator)

    create_response = client.post(reverse("subscriber_create"), subscriber_payload())
    assert create_response.status_code == 302
    subscriber = Subscriber.objects.get()
    assert subscriber.account_number == "SS000001"
    assert subscriber.primary_phone == "+254712345678"

    edit_response = client.post(
        reverse("subscriber_edit", args=[subscriber.pk]),
        subscriber_payload(display_name="Wangari Office", reason="Profile correction"),
    )
    assert edit_response.status_code == 302
    subscriber.refresh_from_db()
    assert subscriber.display_name == "Wangari Office"
    assert subscriber.account_number == "SS000001"

    service_response = client.post(
        reverse("service_create", args=[subscriber.pk]),
        service_payload(),
    )
    assert service_response.status_code == 302
    service = Service.objects.get()
    assert service.service_reference == "SS000001-01"

    service_edit_response = client.post(
        reverse("service_edit", args=[service.pk]),
        service_payload(label="Office service", reason="Label correction"),
    )
    assert service_edit_response.status_code == 302
    service.refresh_from_db()
    assert service.label == "Office service"

    assert (
        client.post(
            reverse("subscriber_deactivate", args=[subscriber.pk]),
            {"reason": "Temporarily inactive"},
        ).status_code
        == 302
    )
    assert (
        client.post(
            reverse("service_deactivate", args=[service.pk]),
            {"reason": "Temporarily inactive"},
        ).status_code
        == 302
    )
    subscriber.refresh_from_db()
    service.refresh_from_db()
    assert subscriber.is_active is False
    assert service.is_active is False
    assert AuditEvent.objects.filter(action="subscriber.created", actor=administrator).exists()
    assert AuditEvent.objects.filter(action="subscriber.updated", actor=administrator).exists()
    assert AuditEvent.objects.filter(action="service.created", actor=administrator).exists()
    assert AuditEvent.objects.filter(action="service.updated", actor=administrator).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("role_name", [ROLE_FINANCE, ROLE_NOC, ROLE_SUPPORT, ROLE_READ_ONLY])
def test_non_admin_roles_cannot_mutate_subscribers_or_services_with_crafted_requests(
    client,
    seeded_roles,
    role_name,
):
    user = create_staff_with_role(
        f"subscriber-crafted-{role_name}".lower().replace(" ", "-"),
        role_name,
    )
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)
    client.force_login(user)

    assert client.post(reverse("subscriber_create"), subscriber_payload()).status_code == 403
    assert (
        client.post(
            reverse("subscriber_edit", args=[subscriber.pk]),
            subscriber_payload(display_name="Crafted edit"),
        ).status_code
        == 403
    )
    assert (
        client.post(reverse("service_create", args=[subscriber.pk]), service_payload()).status_code
        == 403
    )
    assert (
        client.post(
            reverse("service_edit", args=[service.pk]),
            service_payload(label="Crafted service edit"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("subscriber_deactivate", args=[subscriber.pk]),
            {"reason": "crafted"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("service_deactivate", args=[service.pk]),
            {"reason": "crafted"},
        ).status_code
        == 403
    )
    subscriber.refresh_from_db()
    service.refresh_from_db()
    assert subscriber.display_name == "Wangari Home"
    assert subscriber.is_active is True
    assert service.label == "Home fibre"
    assert service.is_active is True


@pytest.mark.django_db
def test_status_routes_are_post_only(client, seeded_roles):
    administrator = create_staff_with_role("subscriber-post-only-admin", ROLE_ADMINISTRATOR)
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)
    client.force_login(administrator)

    assert client.get(reverse("subscriber_deactivate", args=[subscriber.pk])).status_code == 405
    assert client.get(reverse("subscriber_reactivate", args=[subscriber.pk])).status_code == 405
    assert client.get(reverse("service_deactivate", args=[service.pk])).status_code == 405
    assert client.get(reverse("service_reactivate", args=[service.pk])).status_code == 405


@pytest.mark.django_db
def test_audit_metadata_omits_raw_post_and_personal_values(client, seeded_roles):
    administrator = create_staff_with_role("subscriber-audit-admin", ROLE_ADMINISTRATOR)
    client.force_login(administrator)
    response = client.post(
        reverse("subscriber_create"),
        subscriber_payload(csrfmiddlewaretoken="raw-token"),
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="subscriber.created")
    metadata = str(event.safe_metadata)
    assert event.target_identifier == "SS000001"
    assert event.safe_metadata["generated_account_number"] == "SS000001"
    assert "raw-token" not in metadata
    assert "csrfmiddlewaretoken" not in metadata
    assert "reason" not in event.safe_metadata
    assert "Wangari Home" not in metadata
    assert "+254712345678" not in metadata
    assert "wangari@example.test" not in metadata

    subscriber = Subscriber.objects.get()
    client.post(
        reverse("subscriber_edit", args=[subscriber.pk]),
        subscriber_payload(
            display_name="Audit Updated",
            primary_phone="0712444444",
            email="updated@example.test",
            reason="Profile change",
        ),
    )
    update_event = AuditEvent.objects.get(action="subscriber.updated")
    update_metadata = str(update_event.safe_metadata)
    assert update_event.safe_metadata["changed_fields"] == [
        "display_name",
        "primary_phone",
        "email",
    ]
    assert "Audit Updated" not in update_metadata
    assert "+254712444444" not in update_metadata
    assert "updated@example.test" not in update_metadata


@pytest.mark.django_db
def test_dashboard_and_navigation_show_subscribers_only_when_authorized(client, seeded_roles):
    viewer = create_staff_with_role("subscriber-dashboard-viewer", ROLE_READ_ONLY)
    no_role = User.objects.create_user(username="dashboard-no-role", password="StrongPass123!")
    subscriber = create_test_subscriber()
    create_test_service(subscriber)

    client.force_login(no_role)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Subscribers" not in response.content

    client.force_login(viewer)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Subscribers" in response.content
    assert b"1 active subscribers" in response.content
    assert b"1 active services" in response.content


@pytest.mark.django_db
def test_django_admin_cannot_mutate_subscribers_or_services(admin_client):
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)

    subscriber_response = admin_client.post(
        reverse("admin:subscribers_subscriber_change", args=[subscriber.pk]),
        {
            "account_number": "SS999999",
            "display_name": "Admin Changed",
            "primary_phone": "0712555555",
        },
    )
    service_response = admin_client.post(
        reverse("admin:subscribers_service_change", args=[service.pk]),
        {"service_reference": "SS999999-01", "label": "Admin Changed"},
    )

    assert subscriber_response.status_code == 403
    assert service_response.status_code == 403
    subscriber.refresh_from_db()
    service.refresh_from_db()
    assert subscriber.account_number == "SS000001"
    assert subscriber.display_name == "Wangari Home"
    assert service.service_reference == "SS000001-01"
    assert service.label == "Home fibre"
    with pytest.raises((NoReverseMatch, NotRegistered)):
        reverse("admin:subscribers_subscribersequence_changelist")


def test_no_subscriber_or_service_delete_routes():
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(NoReverseMatch):
        reverse("subscriber_delete", args=[fake_uuid])
    with pytest.raises(NoReverseMatch):
        reverse("service_delete", args=[fake_uuid])


def test_phase_3_models_do_not_include_future_domain_fields():
    subscriber_fields = {field.name for field in Subscriber._meta.fields}
    service_fields = {field.name for field in Service._meta.fields}

    assert subscriber_fields == {
        "id",
        "account_number",
        "customer_type",
        "display_name",
        "primary_phone",
        "email",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert service_fields == {
        "id",
        "subscriber",
        "service_number",
        "service_reference",
        "label",
        "is_active",
        "created_at",
        "updated_at",
    }
    forbidden_fields = {
        "national_id",
        "passport",
        "kra_pin",
        "company_registration",
        "date_of_birth",
        "gender",
        "location",
        "plan",
        "package",
        "subscription",
        "price",
        "discount",
        "invoice",
        "payment",
        "wallet",
        "ledger",
        "mpesa",
        "payer",
        "radius",
        "pppoe",
        "router",
        "mac_address",
        "ip_address",
        "installation_fee",
        "equipment",
    }
    assert subscriber_fields.isdisjoint(forbidden_fields)
    assert service_fields.isdisjoint(forbidden_fields)


@pytest.mark.django_db
def test_role_seeding_assigns_subscriber_permissions_without_delete(seeded_roles):
    call_command("seed_roles", verbosity=0)
    call_command("seed_roles", verbosity=0)
    administrator_permissions = set(
        Group.objects.get(name=ROLE_ADMINISTRATOR)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    readonly_permissions = set(
        Group.objects.get(name=ROLE_READ_ONLY)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    sequence_permissions = Permission.objects.filter(
        content_type__app_label="subscribers",
        content_type__model="subscribersequence",
    )

    for model in ["subscriber", "service"]:
        assert ("subscribers", f"view_{model}") in administrator_permissions
        assert ("subscribers", f"add_{model}") in administrator_permissions
        assert ("subscribers", f"change_{model}") in administrator_permissions
        assert ("subscribers", f"delete_{model}") not in administrator_permissions
        assert ("subscribers", f"view_{model}") in readonly_permissions
        assert ("subscribers", f"add_{model}") not in readonly_permissions
        assert ("subscribers", f"change_{model}") not in readonly_permissions
        assert ("subscribers", f"delete_{model}") not in readonly_permissions
    assert not sequence_permissions.exists()
