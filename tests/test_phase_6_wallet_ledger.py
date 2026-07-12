from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Barrier

import pytest
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

import billing.services as billing_services
from audit.models import AuditEvent
from billing.models import LedgerEntry, Wallet
from billing.services import post_manual_wallet_adjustment, reverse_ledger_entry
from subscribers.forms import SubscriberForm
from subscribers.models import Subscriber
from subscribers.services import create_subscriber
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
        "display_name": "Phase Six Subscriber",
        "primary_phone": "0712 345 678",
        "email": "phase6@example.test",
        "reason": "Create subscriber",
    }
    data.update(overrides)
    return data


def valid_subscriber_form(**overrides: str) -> SubscriberForm:
    form = SubscriberForm(data=subscriber_payload(**overrides))
    assert form.is_valid(), form.errors
    return form


def create_test_subscriber(**overrides: str) -> Subscriber:
    return create_subscriber(form=valid_subscriber_form(**overrides), actor=None)


def admin_actor(seeded_roles) -> User:
    return create_staff_with_role("phase6-admin", ROLE_ADMINISTRATOR)


def post_adjustment(
    subscriber: Subscriber,
    actor: User,
    *,
    direction: str = LedgerEntry.DIRECTION_CREDIT,
    amount=Decimal("500"),
    operation_id: uuid.UUID | None = None,
    reason: str = "Manual wallet adjustment",
) -> LedgerEntry:
    return post_manual_wallet_adjustment(
        subscriber=subscriber,
        direction=direction,
        amount=amount,
        operation_id=operation_id or uuid.uuid4(),
        reason=reason,
        actor=actor,
    )


def immutable_test_timestamp() -> datetime:
    return timezone.make_aware(datetime(2001, 1, 1, 12, 0, 0), timezone.get_current_timezone())


@pytest.mark.django_db
def test_viewing_subscriber_without_wallet_shows_zero_without_creating_wallet(client, seeded_roles):
    subscriber = create_test_subscriber()
    viewer = create_staff_with_role("phase6-readonly-zero", ROLE_READ_ONLY)
    client.force_login(viewer)

    response = client.get(reverse("subscriber_detail", args=[subscriber.pk]))

    assert response.status_code == 200
    assert "Wallet" in response.content.decode()
    assert "KSh 0" in response.content.decode()
    assert Wallet.objects.count() == 0


@pytest.mark.django_db
def test_first_adjustment_creates_wallet_and_credit_sequence(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()

    entry = post_adjustment(subscriber, actor, amount=Decimal("1500.50"))

    wallet = Wallet.objects.get(subscriber=subscriber)
    assert entry.wallet == wallet
    assert entry.sequence_number == 1
    assert entry.previous_entry is None
    assert entry.entry_type == LedgerEntry.ENTRY_MANUAL_CREDIT
    assert entry.direction == LedgerEntry.DIRECTION_CREDIT
    assert entry.amount_minor == 150050
    assert entry.balance_after_minor == 150050
    assert wallet.balance_minor == 150050
    assert wallet.formatted_balance == "KSh 1,500.50"
    assert wallet.currency == "KES"


@pytest.mark.django_db
def test_wallet_created_at_cannot_be_changed_through_instance_save(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)
    wallet = entry.wallet
    original_created_at = Wallet.objects.get(pk=wallet.pk).created_at

    wallet.created_at = immutable_test_timestamp()
    with pytest.raises(RuntimeError, match="created_at"):
        wallet.save()

    wallet.refresh_from_db()
    assert wallet.created_at == original_created_at


@pytest.mark.django_db
def test_wallet_created_at_cannot_be_changed_with_update_fields(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)
    wallet = entry.wallet
    original_created_at = Wallet.objects.get(pk=wallet.pk).created_at

    wallet.created_at = immutable_test_timestamp()
    with pytest.raises(RuntimeError, match="created_at"):
        wallet.save(update_fields=["created_at"])

    wallet.refresh_from_db()
    assert wallet.created_at == original_created_at


@pytest.mark.django_db
def test_ledger_entry_created_at_cannot_be_changed_through_instance_save(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)
    original_created_at = LedgerEntry.objects.get(pk=entry.pk).created_at

    entry.created_at = immutable_test_timestamp()
    with pytest.raises(RuntimeError, match="created_at"):
        entry.save()

    entry.refresh_from_db()
    assert entry.created_at == original_created_at


@pytest.mark.django_db
def test_ledger_entry_created_at_cannot_be_changed_with_update_fields(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)
    original_created_at = LedgerEntry.objects.get(pk=entry.pk).created_at

    entry.created_at = immutable_test_timestamp()
    with pytest.raises(RuntimeError, match="created_at"):
        entry.save(update_fields=["created_at"])

    entry.refresh_from_db()
    assert entry.created_at == original_created_at


@pytest.mark.django_db
def test_debit_decreases_balance_and_cannot_go_negative(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    credit = post_adjustment(subscriber, actor, amount=Decimal("500"))
    debit = post_adjustment(
        subscriber,
        actor,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount=Decimal("125.25"),
        reason="Manual debit",
    )

    assert debit.sequence_number == 2
    assert debit.previous_entry == credit
    assert debit.entry_type == LedgerEntry.ENTRY_MANUAL_DEBIT
    assert debit.amount_minor == 12525
    assert debit.balance_after_minor == 37475
    assert debit.wallet.balance_minor == 37475

    with pytest.raises(ValidationError, match="negative"):
        post_adjustment(
            subscriber,
            actor,
            direction=LedgerEntry.DIRECTION_DEBIT,
            amount=Decimal("400"),
            reason="Too much debit",
        )


@pytest.mark.django_db
def test_amount_validation_rejects_zero_negative_precision_and_too_large(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()

    for amount in [Decimal("0"), Decimal("-1"), Decimal("1.999"), Decimal("21474836.48")]:
        with pytest.raises(ValidationError):
            post_adjustment(subscriber, actor, amount=amount, reason=f"Bad {amount}")


@pytest.mark.django_db
def test_latest_balance_matches_credit_minus_debit_sum(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    post_adjustment(subscriber, actor, amount=Decimal("1000"))
    post_adjustment(
        subscriber,
        actor,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount=Decimal("250"),
        reason="Debit",
    )
    post_adjustment(subscriber, actor, amount=Decimal("125.50"), reason="Another credit")
    wallet = Wallet.objects.get(subscriber=subscriber)
    entries = list(wallet.entries.order_by("sequence_number"))

    assert [entry.sequence_number for entry in entries] == [1, 2, 3]
    assert entries[-1].balance_after_minor == 87550
    assert entries[-1].balance_after_minor == sum(
        entry.amount_minor
        if entry.direction == LedgerEntry.DIRECTION_CREDIT
        else -entry.amount_minor
        for entry in entries
    )


@pytest.mark.django_db
def test_wallet_and_ledger_entries_are_append_only(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)
    wallet = entry.wallet

    wallet.currency = "USD"
    with pytest.raises(RuntimeError):
        wallet.save()
    with pytest.raises(RuntimeError):
        Wallet.objects.filter(pk=wallet.pk).update(currency="USD")
    wallet = Wallet.objects.get(pk=wallet.pk)
    wallet.currency = "USD"
    with pytest.raises(RuntimeError):
        Wallet.objects.bulk_update([wallet], ["currency"])
    with pytest.raises(RuntimeError):
        wallet.delete()
    with pytest.raises(RuntimeError):
        Wallet.objects.filter(pk=wallet.pk).delete()

    entry.reason = "Changed"
    with pytest.raises(RuntimeError):
        entry.save()
    with pytest.raises(RuntimeError):
        LedgerEntry.objects.filter(pk=entry.pk).update(reason="Changed")
    entry = LedgerEntry.objects.get(pk=entry.pk)
    entry.amount_minor = 999
    with pytest.raises(RuntimeError):
        LedgerEntry.objects.bulk_update([entry], ["amount_minor"])
    with pytest.raises(RuntimeError):
        entry.delete()
    with pytest.raises(RuntimeError):
        LedgerEntry.objects.filter(pk=entry.pk).delete()


@pytest.mark.django_db
def test_ledger_constraints_and_chain_validation(seeded_roles):
    actor = admin_actor(seeded_roles)
    first_subscriber = create_test_subscriber()
    second_subscriber = create_test_subscriber(primary_phone="0712 345 679")
    first = post_adjustment(first_subscriber, actor)
    other = post_adjustment(second_subscriber, actor)
    invalid = LedgerEntry(
        wallet=other.wallet,
        sequence_number=2,
        operation_id=uuid.uuid4(),
        entry_type=LedgerEntry.ENTRY_MANUAL_CREDIT,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount_minor=100,
        balance_after_minor=other.balance_after_minor + 100,
        previous_entry=first,
        reason="Invalid previous",
        created_by=actor,
    )

    with pytest.raises(ValidationError, match="Previous entry must belong"):
        invalid.full_clean()

    invalid_sequence = LedgerEntry(
        wallet=first.wallet,
        sequence_number=0,
        operation_id=uuid.uuid4(),
        entry_type=LedgerEntry.ENTRY_MANUAL_CREDIT,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount_minor=100,
        balance_after_minor=100,
        previous_entry=None,
        reason="Invalid sequence",
        created_by=actor,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        LedgerEntry.objects.bulk_create([invalid_sequence])


@pytest.mark.django_db
def test_reversals_create_exact_opposite_entries_and_keep_original(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    credit = post_adjustment(subscriber, actor, amount=Decimal("500"))
    debit = post_adjustment(
        subscriber,
        actor,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount=Decimal("100"),
        reason="Debit",
    )
    debit_reversal = reverse_ledger_entry(
        entry=debit,
        operation_id=uuid.uuid4(),
        reason="Reverse debit",
        actor=actor,
    )

    assert debit_reversal.entry_type == LedgerEntry.ENTRY_REVERSAL
    assert debit_reversal.direction == LedgerEntry.DIRECTION_CREDIT
    assert debit_reversal.amount_minor == debit.amount_minor
    assert debit_reversal.reverses_entry == debit
    assert debit_reversal.balance_after_minor == 50000
    debit.refresh_from_db()
    assert debit.entry_type == LedgerEntry.ENTRY_MANUAL_DEBIT

    credit_reversal = reverse_ledger_entry(
        entry=credit,
        operation_id=uuid.uuid4(),
        reason="Reverse credit",
        actor=actor,
    )
    assert credit_reversal.direction == LedgerEntry.DIRECTION_DEBIT
    assert credit_reversal.amount_minor == credit.amount_minor
    assert credit_reversal.balance_after_minor == 0


@pytest.mark.django_db
def test_reversal_rejects_second_reversal_reversal_of_reversal_and_negative_balance(
    seeded_roles,
):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    credit = post_adjustment(subscriber, actor, amount=Decimal("500"))
    debit = post_adjustment(
        subscriber,
        actor,
        direction=LedgerEntry.DIRECTION_DEBIT,
        amount=Decimal("450"),
        reason="Debit",
    )

    with pytest.raises(ValidationError, match="negative"):
        reverse_ledger_entry(
            entry=credit,
            operation_id=uuid.uuid4(),
            reason="Would go negative",
            actor=actor,
        )

    reversal = reverse_ledger_entry(
        entry=debit,
        operation_id=uuid.uuid4(),
        reason="Reverse debit",
        actor=actor,
    )
    with pytest.raises(ValidationError, match="already been reversed"):
        reverse_ledger_entry(
            entry=debit,
            operation_id=uuid.uuid4(),
            reason="Reverse twice",
            actor=actor,
        )
    with pytest.raises(ValidationError, match="cannot reverse another reversal"):
        reverse_ledger_entry(
            entry=reversal,
            operation_id=uuid.uuid4(),
            reason="Reverse reversal",
            actor=actor,
        )


@pytest.mark.django_db
def test_idempotent_adjustment_and_reversal_create_no_duplicate_audit(seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    adjustment_operation = uuid.uuid4()
    first = post_adjustment(subscriber, actor, operation_id=adjustment_operation)
    retry = post_adjustment(subscriber, actor, operation_id=adjustment_operation)

    assert retry.pk == first.pk
    assert LedgerEntry.objects.count() == 1
    assert AuditEvent.objects.filter(action="wallet.manual_credit").count() == 1

    with pytest.raises(ValidationError, match="already used"):
        post_adjustment(
            subscriber,
            actor,
            operation_id=adjustment_operation,
            amount=Decimal("600"),
            reason="Conflicting retry",
        )

    reversal_operation = uuid.uuid4()
    reversal = reverse_ledger_entry(
        entry=first,
        operation_id=reversal_operation,
        reason="Reverse credit",
        actor=actor,
    )
    reversal_retry = reverse_ledger_entry(
        entry=first,
        operation_id=reversal_operation,
        reason="Reverse credit",
        actor=actor,
    )

    assert reversal_retry.pk == reversal.pk
    assert LedgerEntry.objects.count() == 2
    assert AuditEvent.objects.filter(action="wallet.entry_reversed").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role_name", "can_mutate"),
    [
        (ROLE_ADMINISTRATOR, True),
        (ROLE_FINANCE, True),
        (ROLE_SUPPORT, False),
        (ROLE_READ_ONLY, False),
    ],
)
def test_role_based_wallet_mutation_permissions(client, seeded_roles, role_name, can_mutate):
    subscriber = create_test_subscriber()
    user = create_staff_with_role(f"phase6-{role_name}".lower().replace(" ", "-"), role_name)
    client.force_login(user)

    response = client.post(
        reverse("wallet_adjustment", args=[subscriber.pk]),
        {
            "operation_id": uuid.uuid4(),
            "direction": LedgerEntry.DIRECTION_CREDIT,
            "amount_ksh": "100",
            "reason": "Manual credit",
        },
    )

    if can_mutate:
        assert response.status_code == 302
        assert LedgerEntry.objects.filter(wallet__subscriber=subscriber).count() == 1
    else:
        assert response.status_code == 403
        assert Wallet.objects.filter(subscriber=subscriber).count() == 0


@pytest.mark.django_db
def test_noc_cannot_view_wallet_and_crafted_post_is_forbidden(client, seeded_roles):
    subscriber = create_test_subscriber()
    noc = create_staff_with_role("phase6-noc", ROLE_NOC)
    readonly = create_staff_with_role("phase6-craft-readonly", ROLE_READ_ONLY)

    client.force_login(noc)
    assert client.get(reverse("wallet_detail", args=[subscriber.pk])).status_code == 403

    client.force_login(readonly)
    assert (
        client.post(
            reverse("wallet_adjustment", args=[subscriber.pk]),
            {
                "operation_id": uuid.uuid4(),
                "direction": LedgerEntry.DIRECTION_CREDIT,
                "amount_ksh": "100",
                "reason": "Crafted",
            },
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_service_layer_rejects_actor_without_wallet_permissions(seeded_roles):
    actor = create_staff_with_permissions(
        "phase6-no-wallet",
        "subscribers.view_subscriber",
        "billing.view_wallet",
        "billing.view_ledgerentry",
    )
    subscriber = create_test_subscriber()

    with pytest.raises(PermissionDenied):
        post_adjustment(subscriber, actor)


@pytest.mark.django_db
def test_wallet_history_hides_private_data_and_existing_operation_ids(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Private Wallet Subscriber")
    operation_id = uuid.uuid4()
    entry = post_adjustment(
        subscriber,
        actor,
        operation_id=operation_id,
        amount=Decimal("250"),
        reason="Manual credit",
    )
    viewer = create_staff_with_role("phase6-wallet-viewer", ROLE_READ_ONLY)
    client.force_login(viewer)

    response = client.get(reverse("wallet_detail", args=[subscriber.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert subscriber.account_number in content
    assert entry.formatted_amount in content
    assert str(operation_id) not in content
    assert "Private Wallet Subscriber" not in content
    assert "+254712345678" not in content
    assert "phase6@example.test" not in content


@pytest.mark.django_db
def test_audit_metadata_excludes_pii_raw_post_and_operation_id(client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber(display_name="Private Audit Wallet")
    operation_id = uuid.uuid4()
    client.force_login(actor)

    response = client.post(
        reverse("wallet_adjustment", args=[subscriber.pk]),
        {
            "operation_id": operation_id,
            "direction": LedgerEntry.DIRECTION_CREDIT,
            "amount_ksh": "100",
            "reason": "Manual credit",
            "csrfmiddlewaretoken": "raw-token",
        },
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="wallet.manual_credit")
    metadata = str(event.safe_metadata)
    assert subscriber.account_number in metadata
    assert str(operation_id) not in metadata
    assert "raw-token" not in metadata
    assert "csrfmiddlewaretoken" not in metadata
    assert "Private Audit Wallet" not in metadata
    assert "+254712345678" not in metadata
    assert "phase6@example.test" not in metadata


@pytest.mark.django_db
def test_failed_audit_rolls_back_wallet_and_entry(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()

    def fail_audit(**kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(billing_services, "record_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit failed"):
        post_adjustment(subscriber, actor)

    assert Wallet.objects.filter(subscriber=subscriber).count() == 0
    assert LedgerEntry.objects.count() == 0


@pytest.mark.django_db
def test_failed_ledger_creation_produces_no_audit(monkeypatch, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()

    def fail_save(entry):
        raise ValidationError("entry save failed")

    monkeypatch.setattr(billing_services, "_save_ledger_entry", fail_save)
    with pytest.raises(ValidationError, match="entry save failed"):
        post_adjustment(subscriber, actor)

    assert AuditEvent.objects.filter(action__startswith="wallet.").count() == 0


@pytest.mark.django_db
def test_django_admin_cannot_mutate_wallet_or_ledger(admin_client, seeded_roles):
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor)

    wallet_response = admin_client.post(
        reverse("admin:billing_wallet_change", args=[entry.wallet.pk]),
        {"currency": "USD"},
    )
    entry_response = admin_client.post(
        reverse("admin:billing_ledgerentry_change", args=[entry.pk]),
        {"reason": "Changed"},
    )

    assert wallet_response.status_code == 403
    assert entry_response.status_code == 403


@pytest.mark.django_db
def test_role_seeding_assigns_wallet_permissions_without_change_or_delete(seeded_roles):
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
    support_permissions = set(
        Group.objects.get(name=ROLE_SUPPORT)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )
    noc_permissions = set(
        Group.objects.get(name=ROLE_NOC)
        .permissions.order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )

    assert ("billing", "view_wallet") in admin_permissions
    assert ("billing", "view_ledgerentry") in admin_permissions
    assert ("billing", "add_ledgerentry") in admin_permissions
    assert ("billing", "add_wallet") not in admin_permissions
    assert ("billing", "change_wallet") not in admin_permissions
    assert ("billing", "delete_wallet") not in admin_permissions
    assert ("billing", "change_ledgerentry") not in admin_permissions
    assert ("billing", "delete_ledgerentry") not in admin_permissions
    assert ("billing", "add_ledgerentry") in finance_permissions
    assert ("billing", "view_wallet") in support_permissions
    assert ("billing", "add_ledgerentry") not in support_permissions
    assert ("billing", "view_wallet") not in noc_permissions
    assert ("billing", "view_ledgerentry") not in noc_permissions


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_first_credits_create_one_wallet_and_sequential_entries(
    seeded_roles,
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    barrier = Barrier(2)

    def worker(amount):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            entry = post_manual_wallet_adjustment(
                subscriber=Subscriber.objects.get(pk=subscriber.pk),
                direction=LedgerEntry.DIRECTION_CREDIT,
                amount=Decimal(str(amount)),
                operation_id=uuid.uuid4(),
                reason="Concurrent credit",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("created", str(entry.pk))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, 100), executor.submit(worker, 200)]
        results = [future.result() for future in futures]

    assert [status for status, _message in results] == ["created", "created"]
    assert Wallet.objects.filter(subscriber=subscriber).count() == 1
    entries = list(Wallet.objects.get(subscriber=subscriber).entries.order_by("sequence_number"))
    assert [entry.sequence_number for entry in entries] == [1, 2]
    assert entries[-1].balance_after_minor == 30000


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_debits_do_not_make_balance_negative(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    post_adjustment(subscriber, actor, amount=Decimal("100"))
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            entry = post_manual_wallet_adjustment(
                subscriber=Subscriber.objects.get(pk=subscriber.pk),
                direction=LedgerEntry.DIRECTION_DEBIT,
                amount=Decimal("80"),
                operation_id=uuid.uuid4(),
                reason="Concurrent debit",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("created", str(entry.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    wallet = Wallet.objects.get(subscriber=subscriber)
    assert wallet.entries.count() == 2
    assert wallet.balance_minor == 2000


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_duplicate_operation_creates_one_entry(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    operation_id = uuid.uuid4()
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            entry = post_manual_wallet_adjustment(
                subscriber=Subscriber.objects.get(pk=subscriber.pk),
                direction=LedgerEntry.DIRECTION_CREDIT,
                amount=Decimal("100"),
                operation_id=operation_id,
                reason="Duplicate operation",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("created", str(entry.pk))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert len({entry_id for _status, entry_id in results}) == 1
    assert LedgerEntry.objects.filter(wallet__subscriber=subscriber).count() == 1
    assert AuditEvent.objects.filter(action="wallet.manual_credit").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_reversals_create_one_reversal(seeded_roles):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking behavior is verified in CI.")
    actor = admin_actor(seeded_roles)
    subscriber = create_test_subscriber()
    entry = post_adjustment(subscriber, actor, amount=Decimal("100"))
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            reversal = reverse_ledger_entry(
                entry=LedgerEntry.objects.get(pk=entry.pk),
                operation_id=uuid.uuid4(),
                reason="Concurrent reversal",
                actor=User.objects.get(pk=actor.pk),
            )
            return ("created", str(reversal.pk))
        except ValidationError as exc:
            return ("validation", str(exc))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert [status for status, _message in results].count("created") == 1
    assert [status for status, _message in results].count("validation") == 1
    assert LedgerEntry.objects.filter(wallet__subscriber=subscriber).count() == 2
    assert LedgerEntry.objects.filter(reverses_entry=entry).count() == 1


def test_no_wallet_or_ledger_edit_delete_routes():
    with pytest.raises(NoReverseMatch):
        reverse("wallet_edit", args=["00000000-0000-0000-0000-000000000000"])
    with pytest.raises(NoReverseMatch):
        reverse("wallet_delete", args=["00000000-0000-0000-0000-000000000000"])
    with pytest.raises(NoReverseMatch):
        reverse("ledger_entry_edit", args=["00000000-0000-0000-0000-000000000000"])
    with pytest.raises(NoReverseMatch):
        reverse("ledger_entry_delete", args=["00000000-0000-0000-0000-000000000000"])


def test_phase_6_scope_does_not_include_future_payment_or_network_models():
    model_names = {model.__name__.lower() for model in apps.get_models()}
    forbidden_models = {
        "payment",
        "invoice",
        "receipt",
        "discount",
        "renewalcharge",
        "radius",
        "pppoe",
        "routeros",
        "provisioningjob",
        "notification",
    }
    ledger_fields = {field.name.lower() for field in LedgerEntry._meta.fields}

    assert model_names.isdisjoint(forbidden_models)
    assert ledger_fields.isdisjoint(
        {"payment", "mpesa", "paybill", "till", "invoice", "receipt", "network_state"}
    )
