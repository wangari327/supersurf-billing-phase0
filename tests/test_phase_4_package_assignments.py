from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.urls import NoReverseMatch, reverse

import billing.services as billing_services
from audit.models import AuditEvent
from billing.models import Plan, Subscription
from billing.services import assign_package, change_subscription_package, end_subscription
from subscribers.forms import ServiceForm, SubscriberForm
from subscribers.models import Service, Subscriber
from subscribers.services import create_service, create_subscriber
from users.models import User
from users.roles import (
    ROLE_ADMINISTRATOR,
    ROLE_FINANCE,
    ROLE_NOC,
    ROLE_READ_ONLY,
    ROLE_SUPPORT,
)

DETERMINISTIC_SUBSCRIPTION_UUID = uuid.UUID("00000000-0000-0000-0000-000000000401")


def create_staff_with_role(username: str, role_name: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=role_name))
    return user


def create_staff_with_permissions(username: str, *permission_keys: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    for permission_key in permission_keys:
        app_label, codename = permission_key.split(".", maxsplit=1)
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    return user


def subscriber_payload(**overrides: str) -> dict[str, str]:
    data = {
        "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
        "display_name": "Phase Four Subscriber",
        "primary_phone": "0712 345 678",
        "email": "phase4@example.test",
        "reason": "Create subscriber",
    }
    data.update(overrides)
    return data


def valid_subscriber_form(**overrides: str) -> SubscriberForm:
    form = SubscriberForm(data=subscriber_payload(**overrides))
    assert form.is_valid(), form.errors
    return form


def valid_service_form(label: str = "Phase four service") -> ServiceForm:
    form = ServiceForm(data={"label": label, "reason": "Create service"})
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(**overrides: str) -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(**overrides), actor=None)


def create_test_service(subscriber: Subscriber | None = None, *, label: str = "Phase service"):
    subscriber = subscriber or create_test_subscriber()
    return create_service(subscriber=subscriber, form=valid_service_form(label), actor=None)


def create_test_plan(
    name: str = "Phase 4 Package",
    *,
    price_minor: int = 250000,
    is_active: bool = True,
) -> Plan:
    return Plan.objects.create(
        name=name,
        download_speed_mbps=25,
        price_minor=price_minor,
        duration_days=30,
        grace_period_hours=24,
        is_active=is_active,
    )


def admin_actor(seeded_roles) -> User:
    return create_staff_with_role("phase4-admin", ROLE_ADMINISTRATOR)


def assign_test_package(
    service: Service,
    plan: Plan,
    actor: User,
    *,
    reason: str = "Assign package",
) -> Subscription:
    return assign_package(service=service, plan=plan, reason=reason, actor=actor)


@pytest.mark.django_db
def test_first_package_assignment_generates_expected_subscription_uuid(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    plan = create_test_plan()
    field = Subscription._meta.get_field("id")
    original_default = field.default
    field.default = lambda: DETERMINISTIC_SUBSCRIPTION_UUID
    field.__dict__.pop("_get_default", None)
    try:
        subscription = assign_test_package(service, plan, actor)
    finally:
        field.default = original_default
        field.__dict__.pop("_get_default", None)

    assert subscription.pk == DETERMINISTIC_SUBSCRIPTION_UUID
    assert subscription.status == Subscription.STATUS_ACTIVE
    assert subscription.ended_at is None
    assert subscription.starts_at.tzinfo is not None


@pytest.mark.django_db
def test_package_snapshot_matches_package_at_assignment_time(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    plan = create_test_plan(name="Snapshot Package", price_minor=300000)

    subscription = assign_test_package(service, plan, actor)

    assert subscription.plan == plan
    assert subscription.plan_name == "Snapshot Package"
    assert subscription.download_speed_mbps == plan.download_speed_mbps
    assert subscription.price_minor == 300000
    assert subscription.currency == "KES"
    assert subscription.duration_days == 30
    assert subscription.grace_period_hours == 24
    assert subscription.formatted_price == "KSh 3,000"


@pytest.mark.django_db
def test_plan_edit_and_deactivation_do_not_change_existing_snapshot(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    plan = create_test_plan(name="Original Package", price_minor=150000)
    subscription = assign_test_package(service, plan, actor)

    plan.name = "Changed Package"
    plan.download_speed_mbps = 99
    plan.price_minor = 990000
    plan.is_active = False
    plan.save()
    subscription.refresh_from_db()

    assert subscription.plan_name == "Original Package"
    assert subscription.download_speed_mbps == 25
    assert subscription.price_minor == 150000
    assert subscription.status == Subscription.STATUS_ACTIVE


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("plan_active", "service_active", "subscriber_active", "message"),
    [
        (False, True, True, "Only active packages"),
        (True, False, True, "Only active services"),
        (True, True, False, "Only active subscribers"),
    ],
)
def test_assignment_requires_active_plan_service_and_subscriber(
    seeded_roles,
    plan_active,
    service_active,
    subscriber_active,
    message,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    subscriber.is_active = subscriber_active
    subscriber.save()
    service = create_test_service(subscriber)
    service.is_active = service_active
    service.save()
    plan = create_test_plan(is_active=plan_active)

    with pytest.raises(ValidationError, match=message):
        assign_test_package(service, plan, actor)


@pytest.mark.django_db
def test_only_one_active_subscription_per_service_and_duplicate_assignment_rejected(
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="First Package")
    second_plan = create_test_plan(name="Second Package")
    assign_test_package(service, first_plan, actor)

    with pytest.raises(ValidationError, match="already has an active subscription"):
        assign_test_package(service, second_plan, actor)

    assert (
        Subscription.objects.filter(service=service, status=Subscription.STATUS_ACTIVE).count()
        == 1
    )


@pytest.mark.django_db
def test_assignment_uses_service_first_locking_path(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    plan = create_test_plan()
    calls: list[str] = []
    original_service_lock = billing_services._lock_service_and_subscriber
    original_active_lock = billing_services._lock_current_active_subscription
    original_plan_lock = billing_services._lock_selected_plan

    def record_service_lock(service):
        calls.append("service")
        return original_service_lock(service)

    def record_active_lock(service):
        calls.append("subscription")
        return original_active_lock(service)

    def record_plan_lock(plan):
        calls.append("plan")
        return original_plan_lock(plan)

    monkeypatch.setattr(billing_services, "_lock_service_and_subscriber", record_service_lock)
    monkeypatch.setattr(
        billing_services,
        "_lock_current_active_subscription",
        record_active_lock,
    )
    monkeypatch.setattr(billing_services, "_lock_selected_plan", record_plan_lock)

    assign_test_package(service, plan, actor)

    assert calls == ["service", "subscription", "plan"]


@pytest.mark.django_db
def test_package_change_uses_service_first_locking_path(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Lock From")
    second_plan = create_test_plan(name="Lock To")
    subscription = assign_test_package(service, first_plan, actor)
    calls: list[str] = []
    original_service_lock = billing_services._lock_service_and_subscriber_by_id
    original_active_lock = billing_services._lock_current_active_subscription
    original_plan_lock = billing_services._lock_selected_plan

    def record_service_lock(service_id):
        calls.append("service")
        return original_service_lock(service_id)

    def record_active_lock(service):
        calls.append("subscription")
        return original_active_lock(service)

    def record_plan_lock(plan):
        calls.append("plan")
        return original_plan_lock(plan)

    monkeypatch.setattr(
        billing_services,
        "_lock_service_and_subscriber_by_id",
        record_service_lock,
    )
    monkeypatch.setattr(
        billing_services,
        "_lock_current_active_subscription",
        record_active_lock,
    )
    monkeypatch.setattr(billing_services, "_lock_selected_plan", record_plan_lock)

    change_subscription_package(
        subscription=subscription,
        plan=second_plan,
        reason="Change package",
        actor=actor,
    )

    assert calls == ["service", "subscription", "plan"]


@pytest.mark.django_db
def test_subscription_end_uses_service_first_locking_path(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)
    calls: list[str] = []
    original_service_lock = billing_services._lock_service_and_subscriber_by_id
    original_active_lock = billing_services._lock_current_active_subscription

    def record_service_lock(service_id):
        calls.append("service")
        return original_service_lock(service_id)

    def record_active_lock(service):
        calls.append("subscription")
        return original_active_lock(service)

    monkeypatch.setattr(
        billing_services,
        "_lock_service_and_subscriber_by_id",
        record_service_lock,
    )
    monkeypatch.setattr(
        billing_services,
        "_lock_current_active_subscription",
        record_active_lock,
    )

    end_subscription(subscription=subscription, reason="End package", actor=actor)

    assert calls == ["service", "subscription"]


@pytest.mark.django_db
def test_duplicate_assignment_integrity_conflict_returns_validation_error(
    monkeypatch,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Guard One")
    second_plan = create_test_plan(name="Guard Two")
    assign_test_package(service, first_plan, actor)

    monkeypatch.setattr(
        billing_services,
        "_lock_current_active_subscription",
        lambda service: None,
    )

    with pytest.raises(ValidationError, match="already has an active subscription"):
        assign_test_package(service, second_plan, actor)

    assert (
        Subscription.objects.filter(service=service, status=Subscription.STATUS_ACTIVE).count()
        == 1
    )


@pytest.mark.django_db
def test_package_change_ends_old_row_and_creates_new_row_with_same_timestamp(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Change From")
    second_plan = create_test_plan(name="Change To", price_minor=350000)
    old_subscription = assign_test_package(service, first_plan, actor)

    new_subscription = change_subscription_package(
        subscription=old_subscription,
        plan=second_plan,
        reason="Change package",
        actor=actor,
    )
    old_subscription.refresh_from_db()

    assert old_subscription.status == Subscription.STATUS_ENDED
    assert new_subscription.status == Subscription.STATUS_ACTIVE
    assert old_subscription.ended_at == new_subscription.starts_at
    assert new_subscription.plan_name == "Change To"
    assert new_subscription.price_minor == 350000
    assert Subscription.objects.filter(service=service).count() == 2


@pytest.mark.django_db
def test_package_change_rejects_same_or_ended_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    plan = create_test_plan()
    subscription = assign_test_package(service, plan, actor)

    with pytest.raises(ValidationError, match="different active package"):
        change_subscription_package(
            subscription=subscription,
            plan=plan,
            reason="Same package",
            actor=actor,
        )

    ended = end_subscription(subscription=subscription, reason="End package", actor=actor)
    with pytest.raises(ValidationError, match="no longer active"):
        change_subscription_package(
            subscription=ended,
            plan=create_test_plan(name="Replacement Package"),
            reason="Ended change",
            actor=actor,
        )


@pytest.mark.django_db
def test_package_change_rejects_replaced_stale_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Stale From")
    second_plan = create_test_plan(name="Stale To")
    third_plan = create_test_plan(name="Stale Replacement")
    old_subscription = assign_test_package(service, first_plan, actor)
    change_subscription_package(
        subscription=old_subscription,
        plan=second_plan,
        reason="First change",
        actor=actor,
    )

    with pytest.raises(ValidationError, match="no longer active"):
        change_subscription_package(
            subscription=old_subscription,
            plan=third_plan,
            reason="Stale change",
            actor=actor,
        )


@pytest.mark.django_db
def test_ending_rejects_replaced_stale_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="End Stale From")
    second_plan = create_test_plan(name="End Stale To")
    old_subscription = assign_test_package(service, first_plan, actor)
    change_subscription_package(
        subscription=old_subscription,
        plan=second_plan,
        reason="Replace before end",
        actor=actor,
    )

    with pytest.raises(ValidationError, match="no longer active"):
        end_subscription(subscription=old_subscription, reason="End stale", actor=actor)


@pytest.mark.django_db
def test_failed_package_replacement_rolls_back_old_subscription_end(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Rollback From")
    second_plan = create_test_plan(name="Rollback To")
    subscription = assign_test_package(service, first_plan, actor)

    def fail_new_subscription(subscription):
        raise ValidationError("Replacement creation failed.")

    monkeypatch.setattr(billing_services, "_save_new_subscription", fail_new_subscription)

    with pytest.raises(ValidationError, match="Replacement creation failed"):
        change_subscription_package(
            subscription=subscription,
            plan=second_plan,
            reason="Change package",
            actor=actor,
        )

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ACTIVE
    assert subscription.ended_at is None
    assert (
        Subscription.objects.filter(service=service, status=Subscription.STATUS_ACTIVE).count()
        == 1
    )
    assert Subscription.objects.filter(service=service).count() == 1


@pytest.mark.django_db
def test_ending_active_subscription_and_new_assignment_history(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)
    plan = create_test_plan(name="End Me")
    subscription = assign_test_package(service, plan, actor)

    ended = end_subscription(subscription=subscription, reason="End subscription", actor=actor)
    service.refresh_from_db()
    subscriber.refresh_from_db()

    assert ended.status == Subscription.STATUS_ENDED
    assert ended.ended_at is not None
    assert service.is_active is True
    assert subscriber.is_active is True
    with pytest.raises(ValidationError, match="no longer active"):
        end_subscription(subscription=ended, reason="End again", actor=actor)

    new_subscription = assign_test_package(
        service,
        create_test_plan(name="Fresh Assignment"),
        actor,
        reason="Assign again",
    )
    assert new_subscription.pk != ended.pk
    assert Subscription.objects.filter(service=service).count() == 2


@pytest.mark.django_db
def test_ended_subscription_cannot_be_reactivated(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)
    ended = end_subscription(subscription=subscription, reason="End subscription", actor=actor)

    ended.status = Subscription.STATUS_ACTIVE
    ended.ended_at = None
    with pytest.raises(ValidationError, match="Ended subscriptions cannot be reactivated"):
        ended.save()


@pytest.mark.django_db
def test_snapshot_and_identity_fields_are_immutable(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    other_service = create_test_service(label="Other service")
    plan = create_test_plan()
    other_plan = create_test_plan(name="Other Plan")
    subscription = assign_test_package(service, plan, actor)

    subscription.service = other_service
    with pytest.raises(RuntimeError):
        subscription.save()

    with pytest.raises(RuntimeError):
        Subscription.objects.filter(pk=subscription.pk).update(plan=other_plan)

    subscription = Subscription.objects.get(pk=subscription.pk)
    subscription.plan_name = "Changed Snapshot"
    with pytest.raises(RuntimeError):
        Subscription.objects.bulk_update([subscription], ["plan_name"])

    assert Subscription.objects.get(pk=subscription.pk).plan == plan


@pytest.mark.django_db
def test_subscription_deletion_is_rejected(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)

    with pytest.raises(RuntimeError):
        subscription.delete()
    with pytest.raises(RuntimeError):
        Subscription.objects.filter(pk=subscription.pk).delete()


@pytest.mark.django_db
def test_subscription_mutation_routes_are_post_only(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)
    client.force_login(actor)

    assert (
        client.get(reverse("subscription_assign", args=[subscription.service_id])).status_code
        == 405
    )
    assert (
        client.get(reverse("subscription_change_package", args=[subscription.pk])).status_code
        == 405
    )
    assert client.get(reverse("subscription_end", args=[subscription.pk])).status_code == 405


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_assignments_leave_one_active_subscription(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    first_plan = create_test_plan(name="Concurrent Assign One")
    second_plan = create_test_plan(name="Concurrent Assign Two")
    barrier = Barrier(2)

    def worker(plan_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            subscription = assign_package(
                service=Service.objects.get(pk=service.pk),
                plan=Plan.objects.get(pk=plan_id),
                reason="Concurrent assignment",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("created", str(subscription.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, [first_plan.pk, second_plan.pk]))

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    assert any("already has an active subscription" in message for _status, message in results)
    assert (
        Subscription.objects.filter(service=service, status=Subscription.STATUS_ACTIVE).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_change_and_end_leave_consistent_history(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    subscription = assign_test_package(service, create_test_plan(name="Concurrent Base"), actor)
    replacement_plan = create_test_plan(name="Concurrent Replacement")
    barrier = Barrier(2)

    def change_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            new_subscription = change_subscription_package(
                subscription=Subscription.objects.get(pk=subscription.pk),
                plan=Plan.objects.get(pk=replacement_plan.pk),
                reason="Concurrent change",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("changed", str(new_subscription.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    def end_worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            ended_subscription = end_subscription(
                subscription=Subscription.objects.get(pk=subscription.pk),
                reason="Concurrent end",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("ended", str(ended_subscription.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(change_worker), executor.submit(end_worker)]
        results = [future.result() for future in futures]

    successful_statuses = [status for status, _message in results if status != "validation"]
    validation_messages = [message for status, message in results if status == "validation"]
    subscription.refresh_from_db()

    assert len(successful_statuses) == 1
    assert len(validation_messages) == 1
    assert "no longer active" in validation_messages[0]
    assert subscription.status == Subscription.STATUS_ENDED
    assert (
        Subscription.objects.filter(service=service, status=Subscription.STATUS_ACTIVE).count()
        <= 1
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role_name", [ROLE_FINANCE, ROLE_NOC, ROLE_SUPPORT, ROLE_READ_ONLY])
def test_unauthorized_crafted_subscription_mutations_return_403(
    client,
    seeded_roles,
    role_name,
):
    actor = admin_actor(seeded_roles)
    viewer = create_staff_with_role(f"phase4-{role_name}".lower().replace(" ", "-"), role_name)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)
    new_plan = create_test_plan(name=f"Crafted Plan {role_name}")
    client.force_login(viewer)

    assert (
        client.post(
            reverse("subscription_assign", args=[subscription.service_id]),
            {"plan": new_plan.pk, "reason": "crafted"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("subscription_change_package", args=[subscription.pk]),
            {"plan": new_plan.pk, "reason": "crafted"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            reverse("subscription_end", args=[subscription.pk]),
            {"reason": "crafted"},
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_service_layer_rejects_actor_without_subscription_permissions(seeded_roles):
    profile_only = create_staff_with_permissions(
        "phase4-profile-only",
        "subscribers.view_service",
    )

    with pytest.raises(PermissionDenied):
        assign_test_package(create_test_service(), create_test_plan(), profile_only)


@pytest.mark.django_db
def test_profile_only_and_service_only_users_do_not_see_subscription_information(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Subscription Hidden Subscriber")
    service = create_test_service(subscriber, label="Visible service")
    subscription = assign_test_package(service, create_test_plan(name="Hidden Package"), actor)
    profile_only = create_staff_with_permissions(
        "phase4-profile-viewer",
        "subscribers.view_subscriber",
    )
    service_only = create_staff_with_permissions(
        "phase4-service-viewer",
        "subscribers.view_subscriber",
        "subscribers.view_service",
    )

    client.force_login(profile_only)
    profile_response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))
    assert profile_response.status_code == 200
    profile_content = profile_response.content.decode()
    assert "Subscription Hidden Subscriber" in profile_content
    assert service.service_reference not in profile_content
    assert subscription.plan_name not in profile_content

    client.force_login(service_only)
    service_response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))
    assert service_response.status_code == 200
    service_content = service_response.content.decode()
    assert service.service_reference in service_content
    assert "Visible service" in service_content
    assert subscription.plan_name not in service_content
    assert "Assign package" not in service_content
    assert "History" not in service_content


@pytest.mark.django_db
def test_subscription_viewer_sees_history_current_package_and_dashboard_counts(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)
    first = assign_test_package(service, create_test_plan(name="History One"), actor)
    second = change_subscription_package(
        subscription=first,
        plan=create_test_plan(name="History Two"),
        reason="Change package",
        actor=actor,
    )
    viewer = create_staff_with_role("phase4-subscription-viewer", ROLE_READ_ONLY)

    client.force_login(viewer)
    detail_response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))
    assert detail_response.status_code == 200
    detail_content = detail_response.content.decode()
    assert service.service_reference in detail_content
    assert "History Two" in detail_content
    assert "History One" in detail_content
    assert "Active" in detail_content
    assert "Ended" in detail_content
    assert str(second.pk) not in detail_content

    dashboard_response = client.get(reverse("dashboard"))
    assert dashboard_response.status_code == 200
    dashboard_content = dashboard_response.content.decode()
    assert "1 active" in dashboard_content
    assert "1 ended" in dashboard_content


@pytest.mark.django_db
def test_package_detail_subscription_count_requires_view_subscription(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    plan = create_test_plan(name="Counted Package")
    assign_test_package(create_test_service(), plan, actor)
    no_subscription_perm = create_staff_with_permissions("package-no-sub", "billing.view_plan")
    viewer = create_staff_with_role("package-sub-viewer", ROLE_READ_ONLY)

    client.force_login(no_subscription_perm)
    hidden_response = client.get(reverse("package_detail", args=[plan.pk]))
    assert hidden_response.status_code == 200
    assert "Active subscriptions" not in hidden_response.content.decode()

    client.force_login(viewer)
    visible_response = client.get(reverse("package_detail", args=[plan.pk]))
    assert visible_response.status_code == 200
    visible_content = visible_response.content.decode()
    assert "Active subscriptions" in visible_content
    assert ">1<" in visible_content


@pytest.mark.django_db
def test_audit_metadata_omits_raw_post_and_personal_values(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Private Subscriber")
    service = create_test_service(subscriber)
    plan = create_test_plan(name="Audited Package")
    client.force_login(actor)

    response = client.post(
        reverse("subscription_assign", args=[service.pk]),
        {"plan": plan.pk, "reason": "Audit assignment", "csrfmiddlewaretoken": "raw-token"},
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="subscription.assigned")
    metadata = str(event.safe_metadata)
    assert event.reason == "Audit assignment"
    assert "Audited Package" in metadata
    assert service.service_reference in metadata
    assert "raw-token" not in metadata
    assert "csrfmiddlewaretoken" not in metadata
    assert "Private Subscriber" not in metadata
    assert "+254712345678" not in metadata
    assert "phase4@example.test" not in metadata


@pytest.mark.django_db
def test_django_admin_cannot_mutate_subscription(admin_client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscription = assign_test_package(create_test_service(), create_test_plan(), actor)

    response = admin_client.post(
        reverse("admin:billing_subscription_change", args=[subscription.pk]),
        {"status": Subscription.STATUS_ENDED},
    )

    assert response.status_code == 403
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ACTIVE


@pytest.mark.django_db
def test_role_seeding_assigns_subscription_permissions_without_delete(seeded_roles):
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

    assert ("billing", "view_subscription") in administrator_permissions
    assert ("billing", "add_subscription") in administrator_permissions
    assert ("billing", "change_subscription") in administrator_permissions
    assert ("billing", "delete_subscription") not in administrator_permissions
    assert ("billing", "view_subscription") in readonly_permissions
    assert ("billing", "add_subscription") not in readonly_permissions
    assert ("billing", "change_subscription") not in readonly_permissions
    assert ("billing", "delete_subscription") not in readonly_permissions


def test_no_subscription_delete_route():
    with pytest.raises(NoReverseMatch):
        reverse("subscription_delete", args=["00000000-0000-0000-0000-000000000000"])


def test_phase_4_models_do_not_include_future_domain_fields():
    subscription_fields = {field.name for field in Subscription._meta.fields}
    forbidden_fields = {
        "payment",
        "wallet",
        "ledger",
        "invoice",
        "mpesa",
        "discount",
        "radius",
        "pppoe",
        "router",
        "provisioning",
        "installation_fee",
        "equipment",
        "renewal",
        "expiry",
        "grace_state",
    }

    assert subscription_fields == {
        "id",
        "service",
        "plan",
        "status",
        "starts_at",
        "ended_at",
        "plan_name",
        "download_speed_mbps",
        "price_minor",
        "currency",
        "duration_days",
        "grace_period_hours",
        "created_at",
        "updated_at",
    }
    assert subscription_fields.isdisjoint(forbidden_fields)
