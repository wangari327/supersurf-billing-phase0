from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.urls import NoReverseMatch, reverse

import billing.services as billing_services
from audit.models import AuditEvent
from billing.models import BillingCharge, BillingPeriod, LedgerEntry, Plan, Subscription, Wallet
from billing.services import (
    activate_billing_period,
    activate_service_from_wallet,
    assign_package,
    change_subscription_package,
    post_manual_wallet_adjustment,
    renew_service_from_wallet,
    reverse_ledger_entry,
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


def valid_subscriber_form(**overrides: str) -> SubscriberForm:
    data = {
        "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
        "display_name": "Phase Seven Subscriber",
        "primary_phone": "0712 345 678",
        "email": "phase7@example.test",
        "reason": "Create subscriber",
    }
    data.update(overrides)
    form = SubscriberForm(data=data)
    assert form.is_valid(), form.errors
    return form


def valid_service_form(label: str = "Phase seven service") -> ServiceForm:
    form = ServiceForm(data={"label": label, "reason": "Create service"})
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(**overrides: str) -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(**overrides), actor=None)


def create_test_service(subscriber: Subscriber | None = None, *, label: str = "Phase service"):
    subscriber = subscriber or create_test_subscriber()
    return create_service(subscriber=subscriber, form=valid_service_form(label), actor=None)


def create_test_plan(
    name: str = "Phase 7 Package",
    *,
    price_minor: int = 150000,
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
    return create_staff_with_role("phase7-admin", ROLE_ADMINISTRATOR)


def service_with_subscription(
    actor: User,
    *,
    subscriber: Subscriber | None = None,
    plan: Plan | None = None,
    label: str = "Phase seven service",
) -> tuple[Service, Plan]:
    service = create_test_service(subscriber, label=label)
    plan = plan or create_test_plan()
    assign_package(service=service, plan=plan, reason="Assign package", actor=actor)
    return service, plan


def credit_wallet(
    subscriber: Subscriber,
    actor: User,
    *,
    amount=Decimal("1500"),
    operation_id: uuid.UUID | None = None,
) -> LedgerEntry:
    return post_manual_wallet_adjustment(
        subscriber=subscriber,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount=amount,
        operation_id=operation_id or uuid.uuid4(),
        reason="Manual wallet credit",
        actor=actor,
    )


def activate_from_wallet(
    service: Service,
    actor: User,
    *,
    operation_id: uuid.UUID | None = None,
    expected_previous_period_id="",
    effective_at=BASE_TIME,
    reason: str = "Wallet-funded activation",
) -> BillingCharge:
    return activate_service_from_wallet(
        service=service,
        operation_id=operation_id or uuid.uuid4(),
        expected_previous_period_id=expected_previous_period_id,
        reason=reason,
        actor=actor,
        effective_at=effective_at,
    )


def renew_from_wallet(
    service: Service,
    actor: User,
    previous_period: BillingPeriod,
    *,
    operation_id: uuid.UUID | None = None,
    effective_at=BASE_TIME,
    reason: str = "Wallet-funded renewal",
) -> BillingCharge:
    return renew_service_from_wallet(
        service=service,
        operation_id=operation_id or uuid.uuid4(),
        expected_previous_period_id=str(previous_period.pk),
        reason=reason,
        actor=actor,
        effective_at=effective_at,
    )


@pytest.mark.django_db
def test_wallet_funded_activation_exact_balance_links_all_records(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("1500"))
    operation_id = uuid.uuid4()

    charge = activate_from_wallet(service, actor, operation_id=operation_id)

    period = charge.billing_period
    ledger_entry = charge.ledger_entry
    wallet = charge.wallet
    assert charge.charge_type == BillingCharge.CHARGE_ACTIVATION
    assert charge.amount_minor == plan.price_minor == 150000
    assert charge.operation_id == operation_id
    assert period.operation_id == operation_id
    assert ledger_entry.operation_id == operation_id
    assert period.period_type == BillingPeriod.PERIOD_ACTIVATION
    assert ledger_entry.entry_type == LedgerEntry.ENTRY_BILLING_CHARGE
    assert ledger_entry.direction == LedgerEntry.DIRECTION_DEBIT
    assert ledger_entry.balance_after_minor == 0
    assert wallet.balance_minor == 0
    assert charge.service == service
    assert charge.subscription.service == service
    assert charge.wallet.subscriber == service.subscriber
    assert BillingPeriod.objects.filter(service=service).count() == 1
    assert LedgerEntry.objects.filter(wallet=wallet).count() == 2
    assert BillingCharge.objects.count() == 1
    assert AuditEvent.objects.filter(action="billing_period.activated").count() == 1
    assert AuditEvent.objects.filter(action="billing_charge.posted").count() == 1
    assert AuditEvent.objects.filter(action="wallet.billing_charge").count() == 1


@pytest.mark.django_db
def test_wallet_funded_renewal_overpayment_leaves_remaining_credit(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("3500"))
    first_charge = activate_from_wallet(service, actor)

    renewal = renew_from_wallet(
        service,
        actor,
        first_charge.billing_period,
        effective_at=first_charge.billing_period.starts_at + timedelta(days=10),
    )

    assert renewal.charge_type == BillingCharge.CHARGE_RENEWAL
    assert renewal.billing_period.period_type == BillingPeriod.PERIOD_RENEWAL
    assert renewal.billing_period.previous_period == first_charge.billing_period
    assert renewal.billing_period.starts_at == first_charge.billing_period.expires_at
    assert renewal.ledger_entry.sequence_number == 3
    assert renewal.ledger_entry.previous_entry == first_charge.ledger_entry
    assert renewal.ledger_entry.balance_after_minor == 50000
    assert renewal.wallet.balance_minor == 50000


@pytest.mark.django_db
def test_missing_and_insufficient_wallet_reject_without_partial_records(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)

    with pytest.raises(ValidationError, match="existing wallet"):
        activate_from_wallet(service, actor)
    assert Wallet.objects.filter(subscriber=service.subscriber).count() == 0
    assert BillingPeriod.objects.filter(service=service).count() == 0
    assert BillingCharge.objects.count() == 0

    credit = credit_wallet(service.subscriber, actor, amount=Decimal("1000"))
    with pytest.raises(ValidationError, match="insufficient"):
        activate_from_wallet(service, actor, operation_id=uuid.uuid4())

    credit.refresh_from_db()
    assert credit.wallet.balance_minor == 100000
    assert BillingPeriod.objects.filter(service=service).count() == 0
    assert LedgerEntry.objects.filter(wallet=credit.wallet).count() == 1
    assert BillingCharge.objects.count() == 0


@pytest.mark.django_db
def test_subscription_snapshot_controls_charge_amount_after_package_changes(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="Original", price_minor=100000),
    )
    credit_wallet(service.subscriber, actor, amount=Decimal("6000"))
    first = activate_from_wallet(service, actor)
    plan.price_minor = 999000
    plan.save()
    old_subscription = Subscription.objects.get(pk=first.subscription_id)

    second = renew_from_wallet(service, actor, first.billing_period)
    new_plan = create_test_plan(name="New Snapshot", price_minor=300000)
    change_subscription_package(
        subscription=old_subscription,
        plan=new_plan,
        reason="Change package",
        actor=actor,
    )
    third = renew_from_wallet(service, actor, second.billing_period)

    assert first.amount_minor == 100000
    assert second.amount_minor == 100000
    assert third.amount_minor == 300000
    assert third.subscription.plan_name == "New Snapshot"


@pytest.mark.django_db
def test_wallet_funded_date_rules_match_manual_period_rules(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("10000"))
    first = activate_from_wallet(service, actor)
    early = renew_from_wallet(
        service,
        actor,
        first.billing_period,
        effective_at=first.billing_period.starts_at + timedelta(days=10),
    )
    second_early = renew_from_wallet(
        service,
        actor,
        early.billing_period,
        effective_at=first.billing_period.starts_at + timedelta(days=11),
    )
    during_grace = renew_from_wallet(
        service,
        actor,
        second_early.billing_period,
        effective_at=second_early.billing_period.expires_at + timedelta(hours=12),
    )
    late = renew_from_wallet(
        service,
        actor,
        during_grace.billing_period,
        effective_at=during_grace.billing_period.grace_until + timedelta(minutes=1),
    )

    assert early.billing_period.starts_at == first.billing_period.expires_at
    assert second_early.billing_period.starts_at == early.billing_period.expires_at
    assert during_grace.billing_period.starts_at == second_early.billing_period.expires_at
    assert late.billing_period.starts_at == during_grace.billing_period.grace_until + timedelta(
        minutes=1
    )
    assert [
        charge.billing_period.sequence_number
        for charge in [first, early, second_early, during_grace, late]
    ] == [1, 2, 3, 4, 5]


@pytest.mark.django_db
def test_exact_grace_boundary_and_zero_hour_grace(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="No Grace", grace_period_hours=0),
    )
    credit_wallet(service.subscriber, actor, amount=Decimal("5000"))
    first = activate_from_wallet(service, actor)
    renewal = renew_from_wallet(
        service,
        actor,
        first.billing_period,
        effective_at=first.billing_period.grace_until,
    )

    assert first.billing_period.grace_until == first.billing_period.expires_at
    assert renewal.billing_period.starts_at == first.billing_period.grace_until
    assert renewal.billing_period.grace_until == renewal.billing_period.expires_at


@pytest.mark.django_db
def test_billing_charge_records_are_append_only(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor)
    charge = activate_from_wallet(service, actor)
    original_created_at = BillingCharge.objects.get(pk=charge.pk).created_at

    charge.reason = "Changed"
    with pytest.raises(RuntimeError):
        charge.save()
    charge.refresh_from_db()
    assert charge.reason == "Wallet-funded activation"

    charge.created_at = BASE_TIME
    with pytest.raises(RuntimeError, match="created_at"):
        charge.save(update_fields=["created_at"])
    charge.refresh_from_db()
    assert charge.created_at == original_created_at

    with pytest.raises(RuntimeError):
        BillingCharge.objects.filter(pk=charge.pk).update(reason="Changed")
    charge.reason = "Changed"
    with pytest.raises(RuntimeError):
        BillingCharge.objects.bulk_update([charge], ["reason"])
    with pytest.raises(RuntimeError):
        charge.delete()
    with pytest.raises(RuntimeError):
        BillingCharge.objects.filter(pk=charge.pk).delete()


@pytest.mark.django_db
def test_billing_charge_relationship_validation(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("3000"))
    charge = activate_from_wallet(service, actor)
    manual_debit = post_manual_wallet_adjustment(
        subscriber=service.subscriber,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount=Decimal("1"),
        operation_id=uuid.uuid4(),
        reason="Manual debit",
        actor=actor,
    )

    invalid = BillingCharge(
        service=service,
        subscription=charge.subscription,
        billing_period=charge.billing_period,
        wallet=charge.wallet,
        ledger_entry=manual_debit,
        operation_id=charge.operation_id,
        charge_type=BillingCharge.CHARGE_ACTIVATION,
        amount_minor=charge.amount_minor,
        currency="KES",
        reason="Invalid relationship",
        created_by=actor,
    )
    with pytest.raises(ValidationError, match="billing charge"):
        invalid.full_clean()

    invalid_amount = BillingCharge(
        service=service,
        subscription=charge.subscription,
        billing_period=charge.billing_period,
        wallet=charge.wallet,
        ledger_entry=charge.ledger_entry,
        operation_id=charge.operation_id,
        charge_type=BillingCharge.CHARGE_ACTIVATION,
        amount_minor=charge.amount_minor + 1,
        currency="KES",
        reason="Invalid amount",
        created_by=actor,
    )
    with pytest.raises(ValidationError, match="amount"):
        invalid_amount.full_clean()

    invalid_operation = BillingCharge(
        service=service,
        subscription=charge.subscription,
        billing_period=charge.billing_period,
        wallet=charge.wallet,
        ledger_entry=charge.ledger_entry,
        operation_id=uuid.uuid4(),
        charge_type=BillingCharge.CHARGE_ACTIVATION,
        amount_minor=charge.amount_minor,
        currency="KES",
        reason="Invalid operation",
        created_by=actor,
    )
    with pytest.raises(ValidationError, match="operation ID"):
        invalid_operation.full_clean()


@pytest.mark.django_db
def test_billing_charge_ledger_entries_are_not_manual_or_reversible(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor)
    charge = activate_from_wallet(service, actor)
    entry = charge.ledger_entry

    assert entry.entry_type == LedgerEntry.ENTRY_BILLING_CHARGE
    assert entry.direction == LedgerEntry.DIRECTION_DEBIT
    assert entry.is_reversible is False
    with pytest.raises(ValidationError, match="Only manual ledger entries"):
        reverse_ledger_entry(
            entry=entry,
            operation_id=uuid.uuid4(),
            reason="Reverse billing charge",
            actor=actor,
        )

    invalid = LedgerEntry(
        wallet=charge.wallet,
        sequence_number=entry.sequence_number + 1,
        operation_id=uuid.uuid4(),
        entry_type=LedgerEntry.ENTRY_BILLING_CHARGE,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount_minor=100,
        balance_after_minor=entry.balance_after_minor + 100,
        previous_entry=entry,
        reason="Invalid billing charge entry",
        created_by=actor,
    )
    with pytest.raises(ValidationError, match="debit"):
        invalid.full_clean()


@pytest.mark.django_db
def test_charge_idempotency_and_operation_conflicts(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("5000"))
    operation_id = uuid.uuid4()
    first = activate_from_wallet(service, actor, operation_id=operation_id)
    retry = activate_from_wallet(service, actor, operation_id=operation_id)

    assert retry.pk == first.pk
    assert BillingPeriod.objects.filter(service=service).count() == 1
    assert BillingCharge.objects.count() == 1
    assert LedgerEntry.objects.filter(entry_type=LedgerEntry.ENTRY_BILLING_CHARGE).count() == 1
    assert AuditEvent.objects.filter(action="billing_charge.posted").count() == 1

    with pytest.raises(ValidationError, match="different billing charge"):
        activate_from_wallet(
            service,
            actor,
            operation_id=operation_id,
            reason="Different reason",
        )

    other_service, _plan = service_with_subscription(
        actor,
        subscriber=service.subscriber,
        plan=create_test_plan(name="Other"),
    )
    manual_ledger_operation = uuid.uuid4()
    post_manual_wallet_adjustment(
        subscriber=service.subscriber,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount=Decimal("1"),
        operation_id=manual_ledger_operation,
        reason="Manual credit",
        actor=actor,
    )
    with pytest.raises(ValidationError, match="ledger entry"):
        activate_from_wallet(other_service, actor, operation_id=manual_ledger_operation)

    manual_period_service, _plan = service_with_subscription(
        actor,
        plan=create_test_plan(name="Manual"),
    )
    manual_period_operation = uuid.uuid4()
    activate_billing_period(
        service=manual_period_service,
        operation_id=manual_period_operation,
        expected_previous_period_id="",
        reason="Manual period",
        actor=actor,
        effective_at=BASE_TIME,
    )
    credit_wallet(manual_period_service.subscriber, actor, amount=Decimal("2000"))
    with pytest.raises(ValidationError, match="billing period"):
        activate_from_wallet(
            manual_period_service,
            actor,
            operation_id=manual_period_operation,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("helper_name", "message"),
    [
        ("_save_billing_period", "period failed"),
        ("_save_ledger_entry", "ledger failed"),
        ("_save_billing_charge", "charge failed"),
        ("record_event", "audit failed"),
    ],
)
def test_wallet_funded_failures_roll_back_all_records(
    monkeypatch,
    seeded_roles,
    helper_name,
    message,
):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit = credit_wallet(service.subscriber, actor, amount=Decimal("3000"))

    def fail(*args, **kwargs):
        raise RuntimeError(message)

    monkeypatch.setattr(billing_services, helper_name, fail)
    with pytest.raises(RuntimeError, match=message):
        activate_from_wallet(service, actor)

    credit.refresh_from_db()
    assert credit.wallet.balance_minor == 300000
    assert BillingPeriod.objects.filter(service=service).count() == 0
    assert LedgerEntry.objects.filter(entry_type=LedgerEntry.ENTRY_BILLING_CHARGE).count() == 0
    assert BillingCharge.objects.count() == 0
    assert (
        AuditEvent.objects.filter(
            action__in=["billing_charge.posted", "wallet.billing_charge"]
        ).count()
        == 0
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role_name", "can_mutate"),
    [
        (ROLE_ADMINISTRATOR, True),
        (ROLE_FINANCE, True),
        (ROLE_SUPPORT, False),
        (ROLE_READ_ONLY, False),
        (ROLE_NOC, False),
    ],
)
def test_role_based_wallet_funded_mutation_permissions(client, seeded_roles, role_name, can_mutate):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor)
    user = create_staff_with_role(f"phase7-{role_name}".lower().replace(" ", "-"), role_name)
    client.force_login(user)

    response = client.post(
        reverse("wallet_funded_activate", args=[service.pk]),
        {
            "operation_id": uuid.uuid4(),
            "expected_previous_period_id": "",
            "reason": "Activate from Wallet",
        },
    )

    if can_mutate:
        assert response.status_code == 302
        assert BillingCharge.objects.filter(service=service).count() == 1
    else:
        assert response.status_code == 403
        assert BillingCharge.objects.filter(service=service).count() == 0


@pytest.mark.django_db
def test_service_layer_rejects_actor_without_charge_permissions(seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor)
    limited = create_staff_with_permissions(
        "phase7-limited",
        "subscribers.view_subscriber",
        "subscribers.view_service",
        "billing.view_subscription",
        "billing.view_billingperiod",
        "billing.add_billingperiod",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "billing.add_ledgerentry",
        "billing.view_billingcharge",
    )

    with pytest.raises(PermissionDenied):
        activate_from_wallet(service, limited)


@pytest.mark.django_db
def test_role_seeding_assigns_charge_permissions_without_change_or_delete(seeded_roles):
    call_command("seed_roles", verbosity=0)
    call_command("seed_roles", verbosity=0)
    admin_permissions = set(
        Group.objects.get(name=ROLE_ADMINISTRATOR).permissions.values_list(
            "content_type__app_label",
            "codename",
        )
    )
    finance_permissions = set(
        Group.objects.get(name=ROLE_FINANCE).permissions.values_list(
            "content_type__app_label",
            "codename",
        )
    )
    readonly_permissions = set(
        Group.objects.get(name=ROLE_READ_ONLY).permissions.values_list(
            "content_type__app_label",
            "codename",
        )
    )
    noc_permissions = set(
        Group.objects.get(name=ROLE_NOC).permissions.values_list(
            "content_type__app_label",
            "codename",
        )
    )

    assert ("billing", "view_billingcharge") in admin_permissions
    assert ("billing", "add_billingcharge") in admin_permissions
    assert ("billing", "change_billingcharge") not in admin_permissions
    assert ("billing", "delete_billingcharge") not in admin_permissions
    assert ("billing", "add_billingcharge") in finance_permissions
    assert ("billing", "view_billingcharge") in readonly_permissions
    assert ("billing", "add_billingcharge") not in readonly_permissions
    assert ("billing", "view_billingcharge") not in noc_permissions


@pytest.mark.django_db
def test_operator_ui_labels_wallet_funded_and_manual_uncharged_paths(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("3000"))
    client.force_login(actor)

    response = client.get(reverse("subscriber_detail", args=[service.subscriber_id]))
    content = response.content.decode()
    assert "Wallet balance KSh 3,000" in content
    assert "Amount required KSh 1,500" in content
    assert "Remaining balance after charge KSh 1,500" in content
    assert "Activate from Wallet" in content
    assert "Manual uncharged activation" in content
    assert "Manual uncharged periods do not deduct Wallet credit" in content

    charge = activate_from_wallet(service, actor)
    response = client.get(reverse("billing_period_history", args=[service.pk]))
    history = response.content.decode()
    assert "Wallet funded" in history
    assert str(charge.operation_id) not in history

    wallet_response = client.get(reverse("wallet_detail", args=[service.subscriber_id]))
    wallet_content = wallet_response.content.decode()
    assert "Billing charge" in wallet_content
    assert service.service_reference in wallet_content
    assert str(charge.operation_id) not in wallet_content


@pytest.mark.django_db
def test_django_admin_cannot_mutate_billing_charge(admin_client, seeded_roles):
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor)
    charge = activate_from_wallet(service, actor)

    response = admin_client.post(
        reverse("admin:billing_billingcharge_change", args=[charge.pk]),
        {"reason": "Changed"},
    )

    assert response.status_code == 403
    charge.refresh_from_db()
    assert charge.reason == "Wallet-funded activation"


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_duplicate_charge_operation_creates_one_transaction(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("3000"))
    operation_id = uuid.uuid4()
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            charge = activate_service_from_wallet(
                service=Service.objects.get(pk=service.pk),
                operation_id=operation_id,
                expected_previous_period_id="",
                reason="Concurrent charge",
                actor=User.objects.get(pk=actor.pk),
                effective_at=BASE_TIME,
            )
            return ("created", str(charge.pk))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert len({charge_id for _status, charge_id in results}) == 1
    assert BillingCharge.objects.filter(service=service).count() == 1
    assert BillingPeriod.objects.filter(service=service).count() == 1
    assert LedgerEntry.objects.filter(entry_type=LedgerEntry.ENTRY_BILLING_CHARGE).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_same_previous_period_allows_one_renewal(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    service, _plan = service_with_subscription(actor)
    credit_wallet(service.subscriber, actor, amount=Decimal("5000"))
    first = activate_from_wallet(service, actor)
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            charge = renew_service_from_wallet(
                service=Service.objects.get(pk=service.pk),
                operation_id=uuid.uuid4(),
                expected_previous_period_id=str(first.billing_period_id),
                reason="Concurrent renewal",
                actor=User.objects.get(pk=actor.pk),
                effective_at=first.billing_period.expires_at,
            )
            return ("created", str(charge.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    assert BillingCharge.objects.filter(service=service).count() == 2
    assert BillingPeriod.objects.filter(service=service).count() == 2
    assert LedgerEntry.objects.filter(wallet__subscriber=service.subscriber).count() == 3
    assert not BillingPeriod.objects.filter(service=service, sequence_number=3).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_competing_charges_do_not_overdraw_wallet(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    first_service, _plan = service_with_subscription(actor, subscriber=subscriber, label="First")
    second_service, _plan = service_with_subscription(
        actor,
        subscriber=subscriber,
        plan=create_test_plan(name="Second"),
        label="Second",
    )
    credit_wallet(subscriber, actor, amount=Decimal("1500"))
    barrier = Barrier(2)

    def worker(service_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            charge = activate_service_from_wallet(
                service=Service.objects.get(pk=service_id),
                operation_id=uuid.uuid4(),
                expected_previous_period_id="",
                reason="Competing charge",
                actor=User.objects.get(pk=actor.pk),
                effective_at=BASE_TIME,
            )
            return ("created", str(charge.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result()
            for future in [
                executor.submit(worker, first_service.pk),
                executor.submit(worker, second_service.pk),
            ]
        ]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    wallet = Wallet.objects.get(subscriber=subscriber)
    assert wallet.balance_minor == 0
    assert BillingCharge.objects.count() == 1
    sequences = list(
        wallet.entries.order_by("sequence_number").values_list("sequence_number", flat=True)
    )
    assert sequences == [1, 2]


def test_no_billing_charge_edit_delete_routes():
    with pytest.raises(NoReverseMatch):
        reverse("billing_charge_edit", args=["00000000-0000-0000-0000-000000000000"])
    with pytest.raises(NoReverseMatch):
        reverse("billing_charge_delete", args=["00000000-0000-0000-0000-000000000000"])


def test_phase_7_scope_excludes_payments_discounts_automation_and_network_models():
    model_names = {model.__name__.lower() for model in apps.get_models()}
    forbidden_models = {
        "payment",
        "invoice",
        "receipt",
        "discount",
        "bundle",
        "radius",
        "pppoe",
        "routeros",
        "provisioningjob",
        "notification",
        "customerportal",
    }
    charge_fields = {field.name.lower() for field in BillingCharge._meta.fields}

    assert model_names.isdisjoint(forbidden_models)
    assert charge_fields.isdisjoint(
        {"payment", "mpesa", "paybill", "till", "invoice", "receipt", "network_state"}
    )
