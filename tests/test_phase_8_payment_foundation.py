from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import override_settings
from django.urls import reverse

from audit.models import AuditEvent
from billing.models import (
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    Payment,
    PaymentAllocation,
    PaymentProviderProfile,
    Plan,
    UnmatchedPaymentCase,
    Wallet,
)
from billing.services import (
    assign_package,
    ingest_fake_payment,
    post_manual_wallet_adjustment,
    resolve_unmatched_payment,
    reverse_ledger_entry,
)
from subscribers.forms import ServiceForm, SubscriberForm
from subscribers.models import Subscriber
from subscribers.services import create_service, create_subscriber
from users.models import User
from users.roles import (
    ROLE_ADMINISTRATOR,
    ROLE_FINANCE,
    ROLE_NOC,
    ROLE_READ_ONLY,
    ROLE_SUPPORT,
)

BASE_TIME = datetime(2026, 2, 1, 10, 30, tzinfo=UTC)


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


def admin_actor(seeded_roles) -> User:
    return create_staff_with_role("phase8-admin", ROLE_ADMINISTRATOR)


def fake_profile() -> PaymentProviderProfile:
    profile, _created = PaymentProviderProfile.objects.get_or_create(
        provider=PaymentProviderProfile.PROVIDER_FAKE,
        product_type=PaymentProviderProfile.PRODUCT_FAKE,
        environment=PaymentProviderProfile.ENVIRONMENT_TEST,
        external_identifier="fake-test",
        defaults={
            "name": "SuperSurf Fake Test Provider",
            "is_active": True,
        },
    )
    return profile


def valid_subscriber_form(name: str = "Phase Eight Subscriber") -> SubscriberForm:
    form = SubscriberForm(
        data={
            "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
            "display_name": name,
            "primary_phone": "0712 345 678",
            "email": "phase8@example.test",
            "reason": "Create subscriber",
        }
    )
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(name: str = "Phase Eight Subscriber") -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(name), actor=None)


def create_service_with_subscription(subscriber: Subscriber, actor: User):
    form = ServiceForm(data={"label": "Payment service", "reason": "Create service"})
    assert form.is_valid(), form.errors
    service = create_service(subscriber=subscriber, form=form, actor=None)
    plan = Plan.objects.create(
        name=f"Payment Package {uuid.uuid4()}",
        download_speed_mbps=25,
        price_minor=150000,
        duration_days=30,
        grace_period_hours=24,
    )
    assign_package(service=service, plan=plan, reason="Assign package", actor=actor)
    return service


def ingest(
    actor: User,
    *,
    transaction_id: str = "FAKE-TX-1",
    amount=Decimal("1200"),
    account_reference: str = "",
    operation_id: uuid.UUID | None = None,
    profile: PaymentProviderProfile | None = None,
    payload_digest: str = "",
) -> Payment:
    return ingest_fake_payment(
        provider_profile=profile or fake_profile(),
        provider_transaction_id=transaction_id,
        amount=amount,
        received_at=BASE_TIME,
        account_reference=account_reference,
        operation_id=operation_id or uuid.uuid4(),
        actor=actor,
        payload_digest=payload_digest,
    )


@pytest.mark.django_db
def test_matched_fake_payment_credits_wallet_and_normalizes_reference(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    operation_id = uuid.uuid4()

    payment = ingest(
        actor,
        transaction_id="FAKE-MATCH-1",
        amount=Decimal("1200.50"),
        account_reference=f" {subscriber.account_number.lower()} ",
        operation_id=operation_id,
        payload_digest="a" * 64,
    )

    allocation = PaymentAllocation.objects.get(payment=payment)
    entry = allocation.ledger_entry
    wallet = allocation.wallet
    assert payment.account_reference == subscriber.account_number
    assert payment.amount_minor == 120050
    assert payment.payload_digest == "a" * 64
    assert payment.derived_state == "allocated"
    assert allocation.amount_minor == payment.amount_minor
    assert allocation.operation_id == operation_id
    assert wallet.subscriber == subscriber
    assert entry.entry_type == LedgerEntry.ENTRY_PAYMENT_CREDIT
    assert entry.direction == LedgerEntry.DIRECTION_CREDIT
    assert entry.amount_minor == payment.amount_minor
    assert entry.balance_after_minor == 120050
    assert wallet.balance_minor == 120050
    assert BillingPeriod.objects.count() == 0
    assert BillingCharge.objects.count() == 0
    assert AuditEvent.objects.filter(action="payment.received").count() == 1
    assert AuditEvent.objects.filter(action="payment.allocated").count() == 1
    assert AuditEvent.objects.filter(action="wallet.payment_credit").count() == 1
    metadata = AuditEvent.objects.get(action="payment.received").safe_metadata
    assert metadata["account_reference"] == subscriber.account_number
    assert "operation_id" not in metadata
    assert "phase8@example.test" not in str(metadata)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("reference", "reason_code"),
    [
        ("", UnmatchedPaymentCase.REASON_MISSING_REFERENCE),
        ("SS000001-01", UnmatchedPaymentCase.REASON_INVALID_REFERENCE),
        ("SS999999", UnmatchedPaymentCase.REASON_SUBSCRIBER_NOT_FOUND),
    ],
)
def test_unmatched_references_create_cases_without_wallets(seeded_roles, reference, reason_code):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()

    payment = ingest(
        actor,
        transaction_id=f"FAKE-UNMATCHED-{reason_code}",
        account_reference=reference,
    )

    case = UnmatchedPaymentCase.objects.get(payment=payment)
    assert case.status == UnmatchedPaymentCase.STATUS_OPEN
    assert case.reason_code == reason_code
    assert not Wallet.objects.filter(subscriber=subscriber).exists()
    assert PaymentAllocation.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert AuditEvent.objects.filter(action="payment.unmatched").count() == 1


@pytest.mark.django_db
def test_viewing_unmatched_payment_creates_no_wallet(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(actor, transaction_id="FAKE-VIEW-UNMATCHED")
    client.force_login(actor)

    assert client.get(reverse("payment_detail", args=[payment.pk])).status_code == 200
    assert client.get(reverse("unmatched_payment_list")).status_code == 200
    assert not Wallet.objects.filter(subscriber=subscriber).exists()


@pytest.mark.django_db
def test_payment_amounts_remain_wallet_credit_without_service_time(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    create_service_with_subscription(subscriber, actor)

    ingest(
        actor,
        transaction_id="FAKE-PARTIAL-CREDIT",
        amount=Decimal("100"),
        account_reference=subscriber.account_number,
    )
    ingest(
        actor,
        transaction_id="FAKE-OVERPAY-CREDIT",
        amount=Decimal("2000"),
        account_reference=subscriber.account_number,
    )

    wallet = Wallet.objects.get(subscriber=subscriber)
    assert wallet.balance_minor == 210000
    assert BillingPeriod.objects.count() == 0
    assert BillingCharge.objects.count() == 0
    assert PaymentAllocation.objects.count() == 2


@pytest.mark.django_db
def test_successful_unmatched_resolution_and_duplicate_resolution(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(actor, transaction_id="FAKE-RESOLVE", account_reference="SS999999")
    case = UnmatchedPaymentCase.objects.get(payment=payment)
    operation_id = uuid.uuid4()

    allocation = resolve_unmatched_payment(
        unmatched_case=case,
        subscriber=subscriber,
        operation_id=operation_id,
        reason="Resolve to subscriber account",
        actor=actor,
    )
    retry = resolve_unmatched_payment(
        unmatched_case=case,
        subscriber=subscriber,
        operation_id=operation_id,
        reason="Resolve to subscriber account",
        actor=actor,
    )

    case.refresh_from_db()
    assert retry.pk == allocation.pk
    assert case.status == UnmatchedPaymentCase.STATUS_RESOLVED
    assert case.resolution_allocation == allocation
    assert case.resolved_wallet == allocation.wallet
    assert allocation.wallet.subscriber == subscriber
    assert allocation.ledger_entry.entry_type == LedgerEntry.ENTRY_PAYMENT_CREDIT
    assert AuditEvent.objects.filter(action="payment.unmatched_resolved").count() == 1
    with pytest.raises(ValidationError, match="already been resolved"):
        resolve_unmatched_payment(
            unmatched_case=case,
            subscriber=subscriber,
            operation_id=uuid.uuid4(),
            reason="Different resolution",
            actor=actor,
        )


@pytest.mark.django_db
def test_payment_and_allocation_are_immutable(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(
        actor,
        transaction_id="FAKE-IMMUTABLE",
        account_reference=subscriber.account_number,
    )
    allocation = PaymentAllocation.objects.get(payment=payment)
    original_payment_created_at = payment.created_at
    original_allocation_created_at = allocation.created_at

    payment.amount_minor = 1
    with pytest.raises(RuntimeError):
        payment.save()
    payment.refresh_from_db()
    assert payment.amount_minor == 120000

    payment.created_at = BASE_TIME
    with pytest.raises(RuntimeError, match="created_at"):
        payment.save(update_fields=["created_at"])
    payment.refresh_from_db()
    assert payment.created_at == original_payment_created_at

    allocation.amount_minor = 1
    with pytest.raises(RuntimeError):
        allocation.save()
    allocation.refresh_from_db()
    assert allocation.amount_minor == 120000

    allocation.created_at = BASE_TIME
    with pytest.raises(RuntimeError, match="created_at"):
        allocation.save(update_fields=["created_at"])
    allocation.refresh_from_db()
    assert allocation.created_at == original_allocation_created_at

    with pytest.raises(RuntimeError):
        Payment.objects.filter(pk=payment.pk).update(amount_minor=1)
    with pytest.raises(RuntimeError):
        Payment.objects.bulk_update([payment], ["amount_minor"])
    with pytest.raises(RuntimeError):
        Payment.objects.filter(pk=payment.pk).delete()
    with pytest.raises(RuntimeError):
        PaymentAllocation.objects.filter(pk=allocation.pk).update(amount_minor=1)
    with pytest.raises(RuntimeError):
        PaymentAllocation.objects.bulk_update([allocation], ["amount_minor"])
    with pytest.raises(RuntimeError):
        allocation.delete()


@pytest.mark.django_db
def test_payment_provider_transaction_id_rejects_blank_values(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    profile = fake_profile()
    payment = Payment(
        provider_profile=profile,
        provider_transaction_id=" ",
        amount_minor=120000,
        currency="KES",
        received_at=BASE_TIME,
        account_reference=subscriber.account_number,
    )

    with pytest.raises(ValidationError, match="Provider transaction ID is required"):
        payment.full_clean()
    assert Payment.objects.count() == 0

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Payment.objects.bulk_create(
                [
                    Payment(
                        provider_profile=profile,
                        provider_transaction_id="",
                        amount_minor=120000,
                        currency="KES",
                        received_at=BASE_TIME,
                        account_reference=subscriber.account_number,
                    )
                ]
            )

    assert not Payment.objects.filter(provider_transaction_id="").exists()
    created = ingest(
        actor,
        transaction_id="FAKE-NONBLANK-OK",
        account_reference=subscriber.account_number,
    )
    assert created.provider_transaction_id == "FAKE-NONBLANK-OK"


@pytest.mark.django_db
def test_provider_transaction_idempotency_and_conflicts(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    operation_id = uuid.uuid4()
    first = ingest(
        actor,
        transaction_id="FAKE-IDEMPOTENT",
        account_reference=subscriber.account_number,
        operation_id=operation_id,
    )
    retry = ingest(
        actor,
        transaction_id="FAKE-IDEMPOTENT",
        account_reference=f" {subscriber.account_number.lower()} ",
        operation_id=uuid.uuid4(),
    )

    assert retry.pk == first.pk
    assert Payment.objects.count() == 1
    assert PaymentAllocation.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    assert AuditEvent.objects.filter(action="payment.received").count() == 1

    with pytest.raises(ValidationError, match="already used differently"):
        ingest(
            actor,
            transaction_id="FAKE-IDEMPOTENT",
            amount=Decimal("1300"),
            account_reference=subscriber.account_number,
        )


@pytest.mark.django_db
def test_operation_id_conflicts_with_existing_records(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    operation_id = uuid.uuid4()
    post_manual_wallet_adjustment(
        subscriber=subscriber,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount=Decimal("1"),
        operation_id=operation_id,
        reason="Manual credit",
        actor=actor,
    )

    with pytest.raises(ValidationError, match="ledger entry"):
        ingest(
            actor,
            transaction_id="FAKE-OP-CONFLICT",
            account_reference=subscriber.account_number,
            operation_id=operation_id,
        )


@pytest.mark.django_db
def test_payment_credit_entries_are_not_manual_or_reversible(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(
        actor,
        transaction_id="FAKE-NOT-REVERSIBLE",
        account_reference=subscriber.account_number,
    )
    entry = PaymentAllocation.objects.get(payment=payment).ledger_entry

    assert entry.is_reversible is False
    with pytest.raises(ValidationError, match="Only manual ledger entries"):
        reverse_ledger_entry(
            entry=entry,
            operation_id=uuid.uuid4(),
            reason="Reverse payment credit",
            actor=actor,
        )


@pytest.mark.django_db
def test_fake_ingestion_blocked_in_production_and_mpesa_profiles_rejected(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    mpesa_profile = PaymentProviderProfile.objects.create(
        name="M-PESA Sandbox",
        provider=PaymentProviderProfile.PROVIDER_MPESA,
        product_type=PaymentProviderProfile.PRODUCT_PAYBILL,
        environment=PaymentProviderProfile.ENVIRONMENT_SANDBOX,
        external_identifier="123456",
    )

    with pytest.raises(ValidationError, match="Only fake provider"):
        ingest(
            actor,
            transaction_id="MPESA-STRUCTURAL",
            account_reference=subscriber.account_number,
            profile=mpesa_profile,
        )

    with override_settings(SUPERSURF_ENVIRONMENT="PRODUCTION"):
        with pytest.raises(ValidationError, match="production"):
            ingest(
                actor,
                transaction_id="FAKE-PRODUCTION",
                account_reference=subscriber.account_number,
        )


@pytest.mark.django_db
def test_payment_view_only_user_sees_payment_state_without_restricted_details(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    resolved_payment = ingest(
        actor,
        transaction_id="FAKE-VIEW-ONLY-RESOLVED",
        account_reference="SS999999",
    )
    case = UnmatchedPaymentCase.objects.get(payment=resolved_payment)
    allocation = resolve_unmatched_payment(
        unmatched_case=case,
        subscriber=subscriber,
        operation_id=uuid.uuid4(),
        reason="Resolve without exposing destination to payment-only users",
        actor=actor,
    )
    unmatched_payment = ingest(
        actor,
        transaction_id="FAKE-VIEW-ONLY-UNMATCHED",
        account_reference="",
    )
    unmatched_case = UnmatchedPaymentCase.objects.get(payment=unmatched_payment)
    payment_only = create_staff_with_permissions(
        "phase8-payment-only",
        "billing.view_payment",
    )
    client.force_login(payment_only)

    response = client.get(reverse("payment_list"))
    html = response.content.decode()
    assert response.status_code == 200
    assert "FAKE-VIEW-ONLY-RESOLVED" in html
    assert resolved_payment.formatted_amount in html
    assert "Allocated" in html
    assert "New fake payment" not in html
    assert reverse("unmatched_payment_list") not in html

    response = client.get(reverse("payment_detail", args=[resolved_payment.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert "FAKE-VIEW-ONLY-RESOLVED" in html
    assert "SS999999" in html
    assert "Allocated" in html
    assert subscriber.account_number not in html
    assert str(allocation.wallet_id) not in html
    assert str(allocation.pk) not in html
    assert actor.username not in html
    assert "Ledger sequence" not in html
    assert "Balance after" not in html

    response = client.get(reverse("payment_detail", args=[unmatched_payment.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert "Unmatched" in html
    assert "Missing reference" not in html
    assert str(unmatched_case.pk) not in html
    assert reverse("unmatched_payment_resolve", args=[unmatched_case.pk]) not in html
    resolve_response = client.get(reverse("unmatched_payment_resolve", args=[unmatched_case.pk]))
    assert resolve_response.status_code == 403

    response = client.get(reverse("payment_list"), {"q": subscriber.account_number})
    html = response.content.decode()
    assert response.status_code == 200
    assert "FAKE-VIEW-ONLY-RESOLVED" not in html


@pytest.mark.django_db
def test_payment_allocation_permission_without_supporting_views_hides_details(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(actor, transaction_id="FAKE-PARTIAL-ALLOCATION-VIEW", account_reference="")
    case = UnmatchedPaymentCase.objects.get(payment=payment)
    allocation = resolve_unmatched_payment(
        unmatched_case=case,
        subscriber=subscriber,
        operation_id=uuid.uuid4(),
        reason="Resolve to subscriber account",
        actor=actor,
    )
    partial_viewer = create_staff_with_permissions(
        "phase8-partial-allocation-viewer",
        "billing.view_payment",
        "billing.view_paymentallocation",
    )
    client.force_login(partial_viewer)

    response = client.get(reverse("payment_detail", args=[payment.pk]))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Allocated" in html
    assert subscriber.account_number not in html
    assert str(allocation.wallet_id) not in html
    assert "Ledger sequence" not in html
    assert "Balance after" not in html
    assert str(allocation.pk) not in html
    assert actor.username not in html


@pytest.mark.django_db
def test_complete_allocation_view_permissions_show_payment_allocation_details(
    client,
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(actor, transaction_id="FAKE-COMPLETE-ALLOCATION-VIEW", account_reference="")
    case = UnmatchedPaymentCase.objects.get(payment=payment)
    allocation = resolve_unmatched_payment(
        unmatched_case=case,
        subscriber=subscriber,
        operation_id=uuid.uuid4(),
        reason="Resolve to subscriber account",
        actor=actor,
    )
    complete_viewer = create_staff_with_permissions(
        "phase8-complete-allocation-viewer",
        "billing.view_payment",
        "billing.view_paymentallocation",
        "billing.view_wallet",
        "billing.view_ledgerentry",
        "subscribers.view_subscriber",
    )
    client.force_login(complete_viewer)

    response = client.get(reverse("payment_detail", args=[payment.pk]))
    html = response.content.decode()

    assert response.status_code == 200
    assert subscriber.account_number in html
    assert str(allocation.wallet_id) in html
    assert "Ledger sequence" in html
    assert "Balance after" in html
    assert str(allocation.pk) in html
    assert actor.username in html

    response = client.get(reverse("payment_list"), {"q": subscriber.account_number})
    html = response.content.decode()
    assert response.status_code == 200
    assert "FAKE-COMPLETE-ALLOCATION-VIEW" in html


@pytest.mark.django_db
def test_unmatched_payment_list_requires_case_and_payment_visibility(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    payment = ingest(actor, transaction_id="FAKE-UNMATCHED-LIST-PERMS", account_reference="")
    unmatched_only = create_staff_with_permissions(
        "phase8-unmatched-only",
        "billing.view_unmatchedpaymentcase",
    )
    case_and_payment = create_staff_with_permissions(
        "phase8-unmatched-and-payment",
        "billing.view_unmatchedpaymentcase",
        "billing.view_payment",
    )

    client.force_login(unmatched_only)
    assert client.get(reverse("unmatched_payment_list")).status_code == 403

    client.force_login(case_and_payment)
    response = client.get(reverse("unmatched_payment_list"))
    html = response.content.decode()
    assert response.status_code == 200
    assert payment.provider_transaction_id in html
    assert "Resolve" not in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role_name", "can_ingest"),
    [
        (ROLE_ADMINISTRATOR, True),
        (ROLE_FINANCE, True),
        (ROLE_SUPPORT, False),
        (ROLE_READ_ONLY, False),
        (ROLE_NOC, False),
    ],
)
def test_role_based_fake_payment_permissions(client, seeded_roles, role_name, can_ingest):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    user = create_staff_with_role(f"phase8-{role_name}".lower().replace(" ", "-"), role_name)
    client.force_login(user)

    list_response = client.get(reverse("payment_list"))
    if role_name == ROLE_NOC:
        assert list_response.status_code == 403
    else:
        assert list_response.status_code == 200

    response = client.post(
        reverse("fake_payment_create"),
        {
            "provider_profile": fake_profile().pk,
            "provider_transaction_id": f"FAKE-ROLE-{role_name}",
            "amount_ksh": "1200",
            "received_at": "2026-02-01T10:30:00Z",
            "account_reference": subscriber.account_number,
            "payload_digest": "",
            "operation_id": uuid.uuid4(),
        },
    )
    if can_ingest:
        assert response.status_code == 302
        assert Payment.objects.filter(provider_transaction_id=f"FAKE-ROLE-{role_name}").exists()
    else:
        assert response.status_code == 403

    if role_name in {ROLE_SUPPORT, ROLE_READ_ONLY}:
        payment = ingest(
            actor,
            transaction_id=f"FAKE-VIEW-{role_name}",
            account_reference=subscriber.account_number,
        )
        assert client.get(reverse("payment_detail", args=[payment.pk])).status_code == 200


@pytest.mark.django_db
def test_service_layer_rejects_actor_without_payment_permissions(seeded_roles):
    subscriber = create_test_subscriber()
    limited = create_staff_with_permissions(
        "phase8-limited",
        "subscribers.view_subscriber",
        "billing.view_payment",
        "billing.add_payment",
    )

    with pytest.raises(PermissionDenied):
        ingest(
            limited,
            transaction_id="FAKE-LIMITED",
            account_reference=subscriber.account_number,
        )


@pytest.mark.django_db
def test_wallet_history_shows_payment_reference_only_with_payment_visibility(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(
        actor,
        transaction_id="FAKE-WALLET-VISIBILITY",
        account_reference=subscriber.account_number,
    )
    wallet_viewer = create_staff_with_permissions(
        "phase8-wallet-only",
        "subscribers.view_subscriber",
        "billing.view_wallet",
        "billing.view_ledgerentry",
    )
    client.force_login(wallet_viewer)
    response = client.get(reverse("wallet_detail", args=[subscriber.pk]))
    assert response.status_code == 200
    assert payment.provider_transaction_id not in response.content.decode()

    support = create_staff_with_role("phase8-support", ROLE_SUPPORT)
    client.force_login(support)
    response = client.get(reverse("wallet_detail", args=[subscriber.pk]))
    assert payment.provider_transaction_id in response.content.decode()


@pytest.mark.django_db
def test_django_admin_cannot_mutate_payment_records(admin_client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(
        actor,
        transaction_id="FAKE-ADMIN-READONLY",
        account_reference=subscriber.account_number,
    )
    allocation = PaymentAllocation.objects.get(payment=payment)

    payment_response = admin_client.post(
        reverse("admin:billing_payment_change", args=[payment.pk]),
        {"amount_minor": 1},
    )
    allocation_response = admin_client.post(
        reverse("admin:billing_paymentallocation_change", args=[allocation.pk]),
        {"amount_minor": 1},
    )

    assert payment_response.status_code == 403
    assert allocation_response.status_code == 403
    payment.refresh_from_db()
    allocation.refresh_from_db()
    assert payment.amount_minor == 120000
    assert allocation.amount_minor == 120000


@pytest.mark.django_db
def test_role_seeding_assigns_payment_permissions_without_delete(seeded_roles):
    call_command("seed_roles", verbosity=0)
    admin_permissions = set(
        Group.objects.get(name=ROLE_ADMINISTRATOR).permissions.values_list(
            "content_type__app_label",
            "codename",
        )
    )
    support_permissions = set(
        Group.objects.get(name=ROLE_SUPPORT).permissions.values_list(
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

    assert ("billing", "add_payment") in admin_permissions
    assert ("billing", "add_paymentallocation") in admin_permissions
    assert ("billing", "change_payment") not in admin_permissions
    assert ("billing", "delete_payment") not in admin_permissions
    assert ("billing", "view_payment") in support_permissions
    assert ("billing", "add_payment") not in support_permissions
    assert ("billing", "view_payment") not in noc_permissions


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_duplicate_provider_callbacks_create_one_payment(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            payment = ingest_fake_payment(
                provider_profile=PaymentProviderProfile.objects.get(pk=fake_profile().pk),
                provider_transaction_id="FAKE-CONCURRENT-DUPLICATE",
                amount=Decimal("1200"),
                received_at=BASE_TIME,
                account_reference=subscriber.account_number,
                operation_id=uuid.uuid4(),
                actor=User.objects.get(pk=actor.pk),
            )
            return str(payment.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert len(set(results)) == 1
    assert Payment.objects.count() == 1
    assert PaymentAllocation.objects.count() == 1
    assert LedgerEntry.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_credits_preserve_sequence_and_balance(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            payment = ingest_fake_payment(
                provider_profile=PaymentProviderProfile.objects.get(pk=fake_profile().pk),
                provider_transaction_id=f"FAKE-CONCURRENT-CREDIT-{index}",
                amount=Decimal("1200"),
                received_at=BASE_TIME,
                account_reference=subscriber.account_number,
                operation_id=uuid.uuid4(),
                actor=User.objects.get(pk=actor.pk),
            )
            return str(payment.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result()
            for future in [executor.submit(worker, 1), executor.submit(worker, 2)]
        ]

    wallet = Wallet.objects.get(subscriber=subscriber)
    assert len(set(results)) == 2
    assert wallet.balance_minor == 240000
    sequences = list(
        wallet.entries.order_by("sequence_number").values_list("sequence_number", flat=True)
    )
    assert sequences == [
        1,
        2,
    ]


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_unmatched_resolution_creates_one_allocation(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    payment = ingest(actor, transaction_id="FAKE-CONCURRENT-RESOLVE", account_reference="")
    case = UnmatchedPaymentCase.objects.get(payment=payment)
    operation_id = uuid.uuid4()
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            allocation = resolve_unmatched_payment(
                unmatched_case=UnmatchedPaymentCase.objects.get(pk=case.pk),
                subscriber=Subscriber.objects.get(pk=subscriber.pk),
                operation_id=operation_id,
                reason="Concurrent resolution",
                actor=User.objects.get(pk=actor.pk),
            )
            return str(allocation.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert len(set(results)) == 1
    assert PaymentAllocation.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    assert Wallet.objects.get(subscriber=subscriber).balance_minor == 120000


def test_phase_8_scope_excludes_network_invoices_discounts_and_daraja_models():
    model_names = {model.__name__.lower() for model in apps.get_models()}
    forbidden_models = {
        "invoice",
        "receipt",
        "discount",
        "bundle",
        "stkpush",
        "darajacallback",
        "paybillcredential",
        "tillcredential",
        "radius",
        "pppoe",
        "routeros",
        "provisioningjob",
        "notification",
    }
    payment_fields = {field.name.lower() for field in Payment._meta.fields}

    assert model_names.isdisjoint(forbidden_models)
    assert payment_fields.isdisjoint(
        {"raw_payload", "phone", "access_token", "credential", "billing_period", "service"}
    )
