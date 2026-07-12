from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.urls import NoReverseMatch, reverse

import billing.services as billing_services
from audit.models import AuditEvent
from billing.models import BillingPeriod, Plan, Subscription
from billing.services import (
    STALE_BILLING_PERIOD_MESSAGE,
    activate_billing_period,
    assign_package,
    billing_state_for_service,
    change_subscription_package,
    end_subscription,
    renew_billing_period,
)
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

BASE_TIME = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


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
        "display_name": "Phase Five Subscriber",
        "primary_phone": "0712 345 678",
        "email": "phase5@example.test",
        "reason": "Create subscriber",
    }
    data.update(overrides)
    return data


def valid_subscriber_form(**overrides: str) -> SubscriberForm:
    form = SubscriberForm(data=subscriber_payload(**overrides))
    assert form.is_valid(), form.errors
    return form


def valid_service_form(label: str = "Phase five service") -> ServiceForm:
    form = ServiceForm(data={"label": label, "reason": "Create service"})
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(**overrides: str) -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(**overrides), actor=None)


def create_test_service(subscriber: Subscriber | None = None, *, label: str = "Phase service"):
    subscriber = subscriber or create_test_subscriber()
    return create_service(subscriber=subscriber, form=valid_service_form(label), actor=None)


def create_test_plan(
    name: str = "Phase 5 Package",
    *,
    price_minor: int = 250000,
    duration_days: int = 30,
    grace_period_hours: int = 24,
) -> Plan:
    return Plan.objects.create(
        name=name,
        download_speed_mbps=25,
        price_minor=price_minor,
        duration_days=duration_days,
        grace_period_hours=grace_period_hours,
    )


def admin_actor(seeded_roles) -> User:
    return create_staff_with_role("phase5-admin", ROLE_ADMINISTRATOR)


def assign_test_package(service: Service, plan: Plan, actor: User) -> Subscription:
    return assign_package(
        service=service,
        plan=plan,
        reason="Assign package",
        actor=actor,
    )


def activate_test_period(
    service: Service,
    actor: User,
    *,
    operation_id: uuid.UUID | None = None,
    expected_previous_period_id="",
    effective_at=BASE_TIME,
    reason: str = "Activate billing period",
) -> BillingPeriod:
    return activate_billing_period(
        service=service,
        operation_id=operation_id or uuid.uuid4(),
        expected_previous_period_id=expected_previous_period_id,
        reason=reason,
        actor=actor,
        effective_at=effective_at,
    )


def renew_test_period(
    service: Service,
    actor: User,
    previous_period: BillingPeriod,
    *,
    operation_id: uuid.UUID | None = None,
    effective_at=BASE_TIME,
    reason: str = "Renew service",
) -> BillingPeriod:
    return renew_billing_period(
        service=service,
        operation_id=operation_id or uuid.uuid4(),
        expected_previous_period_id=str(previous_period.pk),
        reason=reason,
        actor=actor,
        effective_at=effective_at,
    )


def service_with_subscription(actor: User, *, plan: Plan | None = None) -> tuple[Service, Plan]:
    service = create_test_service()
    plan = plan or create_test_plan()
    assign_test_package(service, plan, actor)
    return service, plan


@pytest.mark.django_db
def test_first_activation_creates_sequence_one_and_snapshots_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, plan = service_with_subscription(actor)

    period = activate_test_period(service, actor)

    assert period.sequence_number == 1
    assert period.period_type == BillingPeriod.PERIOD_ACTIVATION
    assert period.previous_period is None
    assert period.starts_at == BASE_TIME
    assert period.expires_at == BASE_TIME + timedelta(days=30)
    assert period.grace_until == BASE_TIME + timedelta(days=30, hours=24)
    assert period.plan_name == plan.name
    assert period.download_speed_mbps == plan.download_speed_mbps
    assert period.price_minor == plan.price_minor
    assert period.currency == "KES"
    assert period.formatted_price == "KSh 2,500"
    assert period.starts_at.tzinfo is not None
    assert period.expires_at.tzinfo is not None
    assert period.grace_until.tzinfo is not None


@pytest.mark.django_db
def test_plan_edits_and_package_changes_do_not_alter_existing_periods(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="Old Snapshot", price_minor=100000),
    )
    first = activate_test_period(service, actor)
    plan.name = "Edited Plan"
    plan.price_minor = 999000
    plan.save()
    old_subscription = Subscription.objects.get(pk=first.subscription_id)
    new_plan = create_test_plan(name="New Snapshot", price_minor=300000)
    change_subscription_package(
        subscription=old_subscription,
        plan=new_plan,
        reason="Change package",
        actor=actor,
    )

    second = renew_test_period(
        service,
        actor,
        first,
        effective_at=first.starts_at + timedelta(days=2),
    )
    first.refresh_from_db()

    assert first.plan_name == "Old Snapshot"
    assert first.price_minor == 100000
    assert second.plan_name == "New Snapshot"
    assert second.price_minor == 300000
    assert second.starts_at == first.expires_at


@pytest.mark.django_db
def test_billing_period_fields_are_append_only(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    period = activate_test_period(service, actor)

    period.plan_name = "Changed"
    with pytest.raises(RuntimeError):
        period.save()

    with pytest.raises(RuntimeError):
        BillingPeriod.objects.filter(pk=period.pk).update(plan_name="Changed")

    period = BillingPeriod.objects.get(pk=period.pk)
    period.price_minor = 999
    with pytest.raises(RuntimeError):
        BillingPeriod.objects.bulk_update([period], ["price_minor"])

    with pytest.raises(RuntimeError):
        period.delete()
    with pytest.raises(RuntimeError):
        BillingPeriod.objects.filter(pk=period.pk).delete()


@pytest.mark.django_db
def test_database_constraints_and_previous_period_service_validation(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    period = activate_test_period(service, actor)
    other_service, _other_plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="Other"),
    )
    invalid_previous = BillingPeriod(
        service=other_service,
        subscription=Subscription.objects.get(
            service=other_service,
            status=Subscription.STATUS_ACTIVE,
        ),
        sequence_number=1,
        period_type=BillingPeriod.PERIOD_RENEWAL,
        operation_id=uuid.uuid4(),
        previous_period=period,
        effective_at=period.expires_at,
        starts_at=period.expires_at,
        expires_at=period.expires_at + timedelta(days=30),
        grace_until=period.expires_at + timedelta(days=31),
        plan_name=period.plan_name,
        download_speed_mbps=period.download_speed_mbps,
        price_minor=period.price_minor,
        currency="KES",
        duration_days=30,
        grace_period_hours=24,
    )
    with pytest.raises(ValidationError, match="Previous period must belong"):
        invalid_previous.full_clean()

    invalid = BillingPeriod(
        service=service,
        subscription=period.subscription,
        sequence_number=0,
        period_type=BillingPeriod.PERIOD_RENEWAL,
        operation_id=uuid.uuid4(),
        previous_period=period,
        effective_at=period.expires_at,
        starts_at=period.expires_at,
        expires_at=period.expires_at + timedelta(days=30),
        grace_until=period.expires_at + timedelta(days=31),
        plan_name=period.plan_name,
        download_speed_mbps=period.download_speed_mbps,
        price_minor=period.price_minor,
        currency="KES",
        duration_days=30,
        grace_period_hours=24,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        BillingPeriod.objects.bulk_create([invalid])


@pytest.mark.django_db
def test_renewal_date_rules(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)
    early = renew_test_period(
        service,
        actor,
        first,
        effective_at=first.starts_at + timedelta(days=10),
    )
    second_early = renew_test_period(
        service,
        actor,
        early,
        effective_at=first.starts_at + timedelta(days=11),
    )
    during_grace = renew_test_period(
        service,
        actor,
        second_early,
        effective_at=second_early.expires_at + timedelta(hours=12),
    )
    late = renew_test_period(
        service,
        actor,
        during_grace,
        effective_at=during_grace.grace_until + timedelta(minutes=1),
    )

    assert early.starts_at == first.expires_at
    assert early.expires_at == first.expires_at + timedelta(days=30)
    assert second_early.starts_at == early.expires_at
    assert during_grace.starts_at == second_early.expires_at
    assert late.starts_at == during_grace.grace_until + timedelta(minutes=1)
    sequence_numbers = [
        period.sequence_number for period in [first, early, second_early, during_grace, late]
    ]
    assert sequence_numbers == [1, 2, 3, 4, 5]


@pytest.mark.django_db
def test_exact_grace_boundary_is_late_and_zero_hour_grace_works(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="No Grace", grace_period_hours=0),
    )
    first = activate_test_period(service, actor)
    renewal = renew_test_period(service, actor, first, effective_at=first.grace_until)

    assert first.grace_until == first.expires_at
    assert renewal.starts_at == first.grace_until
    assert renewal.grace_until == renewal.expires_at


@pytest.mark.django_db
def test_multiple_services_keep_independent_dates(seeded_roles):
    actor = admin_actor(seeded_roles)
    first_service, _plan = service_with_subscription(actor)
    second_service, _plan = service_with_subscription(actor, plan=create_test_plan(name="Second"))

    first_period = activate_test_period(first_service, actor, effective_at=BASE_TIME)
    second_period = activate_test_period(
        second_service,
        actor,
        effective_at=BASE_TIME + timedelta(days=5),
    )

    assert first_period.expires_at == BASE_TIME + timedelta(days=30)
    assert second_period.expires_at == BASE_TIME + timedelta(days=35)


@pytest.mark.django_db
def test_derived_states_do_not_mutate_service_subscriber_or_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    subscription = Subscription.objects.get(service=service, status=Subscription.STATUS_ACTIVE)

    assert billing_state_for_service(service, BASE_TIME) == "unactivated"
    period = activate_test_period(service, actor)
    assert billing_state_for_service(service, period.starts_at + timedelta(days=1)) == "active"
    assert billing_state_for_service(service, period.expires_at) == "grace"
    assert billing_state_for_service(service, period.grace_until) == "expired"
    service.refresh_from_db()
    service.subscriber.refresh_from_db()
    subscription.refresh_from_db()
    assert service.is_active is True
    assert service.subscriber.is_active is True
    assert subscription.status == Subscription.STATUS_ACTIVE


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subscriber_active", "service_active", "message"),
    [
        (False, True, "Only active subscribers"),
        (True, False, "Only active services"),
    ],
)
def test_activation_requires_active_subscriber_and_service(
    seeded_roles,
    subscriber_active,
    service_active,
    message,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    service = create_test_service(subscriber)
    assign_test_package(service, create_test_plan(), actor)
    subscriber.is_active = subscriber_active
    subscriber.save()
    service.is_active = service_active
    service.save()

    with pytest.raises(ValidationError, match=message):
        activate_test_period(service, actor)


@pytest.mark.django_db
def test_billing_period_creation_requires_active_subscription(seeded_roles):
    actor = admin_actor(seeded_roles)
    service = create_test_service()
    with pytest.raises(ValidationError, match="current active subscription"):
        activate_test_period(service, actor)

    assign_test_package(service, create_test_plan(), actor)
    subscription = Subscription.objects.get(service=service, status=Subscription.STATUS_ACTIVE)
    end_subscription(subscription=subscription, reason="End subscription", actor=actor)
    with pytest.raises(ValidationError, match="current active subscription"):
        activate_test_period(service, actor)


@pytest.mark.django_db
def test_activation_and_renewal_history_requirements(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)

    with pytest.raises(ValidationError, match="history already exists"):
        activate_test_period(service, actor)
    with pytest.raises(ValidationError, match="First activation cannot include"):
        activate_test_period(service, actor, expected_previous_period_id=str(first.pk))
    with pytest.raises(ValidationError, match="Renewal requires the latest"):
        renew_billing_period(
            service=service,
            operation_id=uuid.uuid4(),
            expected_previous_period_id="",
            reason="Renew",
            actor=actor,
            effective_at=first.expires_at,
        )

    second_service, _plan = service_with_subscription(actor, plan=create_test_plan(name="Fresh"))
    with pytest.raises(ValidationError, match="existing billing period"):
        renew_billing_period(
            service=second_service,
            operation_id=uuid.uuid4(),
            expected_previous_period_id=str(uuid.uuid4()),
            reason="Renew",
            actor=actor,
            effective_at=first.expires_at,
        )


@pytest.mark.django_db
def test_operation_id_idempotency_and_conflict_detection(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    operation_id = uuid.uuid4()
    first = activate_test_period(service, actor, operation_id=operation_id)
    retry = activate_test_period(service, actor, operation_id=operation_id)

    assert retry.pk == first.pk
    assert AuditEvent.objects.filter(action="billing_period.activated").count() == 1

    with pytest.raises(ValidationError, match="already used"):
        renew_billing_period(
            service=service,
            operation_id=operation_id,
            expected_previous_period_id=str(first.pk),
            reason="Conflicting operation",
            actor=actor,
            effective_at=first.expires_at,
        )


@pytest.mark.django_db
def test_stale_renewal_leaves_history_unchanged(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)
    second = renew_test_period(service, actor, first, effective_at=first.expires_at)

    with pytest.raises(ValidationError, match=STALE_BILLING_PERIOD_MESSAGE):
        renew_test_period(service, actor, first, effective_at=first.expires_at)

    assert BillingPeriod.objects.filter(service=service).count() == 2
    assert BillingPeriod.objects.get(pk=second.pk).sequence_number == 2


@pytest.mark.django_db
def test_failed_audit_rolls_back_period_and_failed_period_creates_no_audit(
    monkeypatch,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)

    def fail_audit(**kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(billing_services, "record_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit failed"):
        activate_test_period(service, actor)
    assert BillingPeriod.objects.filter(service=service).count() == 0

    monkeypatch.setattr(billing_services, "record_event", lambda **kwargs: None)

    def fail_save(period):
        raise ValidationError("period save failed")

    monkeypatch.setattr(billing_services, "_save_billing_period", fail_save)
    with pytest.raises(ValidationError, match="period save failed"):
        activate_test_period(service, actor, operation_id=uuid.uuid4())
    assert AuditEvent.objects.filter(action__startswith="billing_period.").count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_activation_creates_one_period(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            period = activate_billing_period(
                service=Service.objects.get(pk=service.pk),
                operation_id=uuid.uuid4(),
                expected_previous_period_id="",
                reason="Concurrent activation",
                actor=User.objects.get(pk=actor.pk),
                effective_at=BASE_TIME,
            )
            return ("created", str(period.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    assert BillingPeriod.objects.filter(service=service).count() == 1
    sequence_numbers = list(
        BillingPeriod.objects.filter(service=service).values_list("sequence_number", flat=True)
    )
    assert sequence_numbers == [1]


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_renewal_creates_one_successor(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            period = renew_billing_period(
                service=Service.objects.get(pk=service.pk),
                operation_id=uuid.uuid4(),
                expected_previous_period_id=str(first.pk),
                reason="Concurrent renewal",
                actor=User.objects.get(pk=actor.pk),
                effective_at=first.expires_at,
            )
            return ("created", str(period.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    assert BillingPeriod.objects.filter(service=service).count() == 2
    assert list(
        BillingPeriod.objects.filter(service=service).order_by("sequence_number").values_list(
            "sequence_number",
            flat=True,
        )
    ) == [1, 2]
    assert BillingPeriod.objects.filter(previous_period=first).count() == 1


@pytest.mark.django_db
def test_service_layer_rejects_actor_without_period_permissions(seeded_roles):
    actor = create_staff_with_permissions(
        "phase5-no-period-add",
        "subscribers.view_service",
        "billing.view_subscription",
    )
    service, _plan = service_with_subscription(admin_actor(seeded_roles))

    with pytest.raises(PermissionDenied):
        activate_test_period(service, actor)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role_name", "can_mutate"),
    [
        (ROLE_ADMINISTRATOR, True),
        (ROLE_FINANCE, True),
        (ROLE_NOC, False),
        (ROLE_SUPPORT, False),
        (ROLE_READ_ONLY, False),
    ],
)
def test_role_based_period_mutation_permissions(client, seeded_roles, role_name, can_mutate):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    user = create_staff_with_role(f"phase5-{role_name}".lower().replace(" ", "-"), role_name)
    client.force_login(user)

    response = client.post(
        reverse("billing_period_activate", args=[service.pk]),
        {
            "operation_id": uuid.uuid4(),
            "expected_previous_period_id": "",
            "reason": "Activate",
        },
    )

    if can_mutate:
        assert response.status_code == 302
        assert BillingPeriod.objects.filter(service=service).count() == 1
    else:
        assert response.status_code == 403
        assert BillingPeriod.objects.filter(service=service).count() == 0


@pytest.mark.django_db
def test_finance_can_renew_after_activation(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)
    finance = create_staff_with_role("phase5-finance-renewer", ROLE_FINANCE)
    client.force_login(finance)

    response = client.post(
        reverse("billing_period_renew", args=[service.pk]),
        {
            "operation_id": uuid.uuid4(),
            "expected_previous_period_id": str(first.pk),
            "reason": "Renew",
        },
    )

    assert response.status_code == 302
    assert BillingPeriod.objects.filter(service=service).count() == 2


@pytest.mark.django_db
def test_period_visibility_requires_service_subscription_and_period_permissions(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Billing Hidden Subscriber")
    service = create_test_service(subscriber, label="Billing Visible Service")
    assign_test_package(service, create_test_plan(name="Hidden Billing Package"), actor)
    period = activate_test_period(service, actor)
    profile_only = create_staff_with_permissions(
        "phase5-profile-only",
        "subscribers.view_subscriber",
    )
    service_only = create_staff_with_permissions(
        "phase5-service-only",
        "subscribers.view_subscriber",
        "subscribers.view_service",
    )
    subscription_only = create_staff_with_permissions(
        "phase5-subscription-only",
        "subscribers.view_subscriber",
        "subscribers.view_service",
        "billing.view_subscription",
    )
    viewer = create_staff_with_role("phase5-viewer", ROLE_READ_ONLY)

    for user in [profile_only, service_only, subscription_only]:
        client.force_login(user)
        response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Billing Hidden Subscriber" in content
        assert "Billing periods" not in content
        assert "Network enforcement is not implemented" not in content
        assert "Renew service" not in content

    client.force_login(viewer)
    response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))
    content = response.content.decode()
    assert response.status_code == 200
    assert period.plan_name in content
    assert "Network enforcement is not implemented" in content
    assert "Renew service" not in content


@pytest.mark.django_db
def test_history_page_protected_and_does_not_show_operation_id(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    period = activate_test_period(service, actor)
    profile_only = create_staff_with_permissions(
        "phase5-history-profile",
        "subscribers.view_subscriber",
    )
    viewer = create_staff_with_role("phase5-history-viewer", ROLE_READ_ONLY)

    client.force_login(profile_only)
    assert client.get(reverse("billing_period_history", args=[service.pk])).status_code == 403

    client.force_login(viewer)
    response = client.get(reverse("billing_period_history", args=[service.pk]))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Billing periods" in content
    assert str(period.operation_id) not in content


@pytest.mark.django_db
def test_period_actions_are_post_only_and_crafted_requests_return_403(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    first = activate_test_period(service, actor)
    readonly = create_staff_with_role("phase5-crafted-readonly", ROLE_READ_ONLY)

    client.force_login(actor)
    assert client.get(reverse("billing_period_activate", args=[service.pk])).status_code == 405
    assert client.get(reverse("billing_period_renew", args=[service.pk])).status_code == 405

    client.force_login(readonly)
    assert (
        client.post(
            reverse("billing_period_renew", args=[service.pk]),
            {
                "operation_id": uuid.uuid4(),
                "expected_previous_period_id": str(first.pk),
                "reason": "Crafted",
            },
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_audit_metadata_excludes_pii_raw_post_and_operation_id(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Private Billing Subscriber")
    service = create_test_service(subscriber)
    assign_test_package(service, create_test_plan(name="Audited Period Package"), actor)
    operation_id = uuid.uuid4()
    client.force_login(actor)

    response = client.post(
        reverse("billing_period_activate", args=[service.pk]),
        {
            "operation_id": operation_id,
            "expected_previous_period_id": "",
            "reason": "Activate billing",
            "csrfmiddlewaretoken": "raw-token",
        },
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="billing_period.activated")
    metadata = str(event.safe_metadata)
    assert "Audited Period Package" in metadata
    assert service.service_reference in metadata
    assert str(operation_id) not in metadata
    assert "raw-token" not in metadata
    assert "csrfmiddlewaretoken" not in metadata
    assert "Private Billing Subscriber" not in metadata
    assert "+254712345678" not in metadata
    assert "phase5@example.test" not in metadata


@pytest.mark.django_db
def test_django_admin_cannot_mutate_billing_period(admin_client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    period = activate_test_period(service, actor)

    response = admin_client.post(
        reverse("admin:billing_billingperiod_change", args=[period.pk]),
        {"plan_name": "Changed"},
    )

    assert response.status_code == 403
    period.refresh_from_db()
    assert period.plan_name != "Changed"


@pytest.mark.django_db
def test_role_seeding_assigns_period_permissions_without_change_or_delete(seeded_roles):
    call_command("seed_roles", verbosity=0)
    call_command("seed_roles", verbosity=0)
    admin_permissions = set(
        Group.objects.get(name=ROLE_ADMINISTRATOR)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    finance_permissions = set(
        Group.objects.get(name=ROLE_FINANCE)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    readonly_permissions = set(
        Group.objects.get(name=ROLE_READ_ONLY)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )

    assert ("billing", "view_billingperiod") in admin_permissions
    assert ("billing", "add_billingperiod") in admin_permissions
    assert ("billing", "change_billingperiod") not in admin_permissions
    assert ("billing", "delete_billingperiod") not in admin_permissions
    assert ("billing", "add_billingperiod") in finance_permissions
    assert ("billing", "view_billingperiod") in readonly_permissions
    assert ("billing", "add_billingperiod") not in readonly_permissions


@pytest.mark.django_db
def test_dashboard_counts_billing_states_only_with_required_visibility(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    active_service, _plan = service_with_subscription(actor)
    grace_service, _plan = service_with_subscription(actor, plan=create_test_plan(name="Grace"))
    expired_service, _plan = service_with_subscription(actor, plan=create_test_plan(name="Expired"))
    create_test_service(label="Unactivated")
    active_period = activate_test_period(active_service, actor)
    grace_period = activate_test_period(
        grace_service,
        actor,
        effective_at=BASE_TIME - timedelta(days=30),
    )
    activate_test_period(expired_service, actor, effective_at=BASE_TIME - timedelta(days=40))
    no_period_viewer = create_staff_with_permissions(
        "phase5-dashboard-hidden",
        "subscribers.view_service",
        "billing.view_subscription",
    )
    viewer = create_staff_with_role("phase5-dashboard-viewer", ROLE_READ_ONLY)

    assert billing_state_for_service(active_service, active_period.starts_at) == "active"
    assert billing_state_for_service(grace_service, grace_period.expires_at) == "grace"

    client.force_login(no_period_viewer)
    hidden_response = client.get(reverse("dashboard"))
    assert "Billing periods" not in hidden_response.content.decode()

    client.force_login(viewer)
    response = client.get(reverse("dashboard"))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Billing periods" in content
    assert "network enforcement is not implemented" in content


def test_no_billing_period_delete_or_edit_routes():
    with pytest.raises(NoReverseMatch):
        reverse("billing_period_delete", args=["00000000-0000-0000-0000-000000000000"])
    with pytest.raises(NoReverseMatch):
        reverse("billing_period_edit", args=["00000000-0000-0000-0000-000000000000"])


def test_phase_5_scope_does_not_include_future_billing_or_network_models():
    model_names = {model.__name__.lower() for model in apps.get_models()}
    forbidden_models = {
        "invoice",
        "receipt",
        "discount",
        "webhookevent",
        "mpesapayment",
        "radius",
        "pppoe",
        "routeros",
        "provisioningjob",
        "notification",
    }
    period_fields = {field.name for field in BillingPeriod._meta.fields}

    assert model_names.isdisjoint(forbidden_models)
    assert period_fields.isdisjoint(
        {"payment", "wallet", "ledger", "invoice", "mpesa", "discount", "network_state"}
    )
