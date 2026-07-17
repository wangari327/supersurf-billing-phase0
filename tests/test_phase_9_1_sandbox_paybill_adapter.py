from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from threading import Barrier

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
from billing.models import (
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    MpesaCallbackEvent,
    MpesaCallbackPaymentLink,
    Payment,
    PaymentAllocation,
    PaymentProviderProfile,
    UnmatchedPaymentCase,
    Wallet,
)
from billing.mpesa_callbacks import capture_mpesa_callback
from billing.services import (
    PaybillProfileUnavailable,
    ingest_fake_payment,
    process_mpesa_paybill_confirmation_event,
)
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

TOKEN = "b" * 64
IDENTIFIER = "654321"
ENABLED_SETTINGS = {
    "SUPERSURF_ENVIRONMENT": "LAB",
    "SUPERSURF_PUBLIC_DEPLOYMENT": True,
    "MPESA_CALLBACK_TOKEN": TOKEN,
    "MPESA_PAYBILL_INGESTION_ENABLED": True,
    "MPESA_PAYBILL_EXTERNAL_IDENTIFIER": IDENTIFIER,
}


def c2b_payload(**overrides):
    payload = {
        "TransID": "P91SYNTHETIC001",
        "TransAmount": "1.00",
        "BusinessShortCode": IDENTIFIER,
        "BillRefNumber": "SS000001",
        "MSISDN": "254700000001",
        "FirstName": "Synthetic",
        "OrgAccountBalance": "999.00",
    }
    payload.update(overrides)
    return payload


def post_confirmation(client, payload):
    return client.post(
        reverse("mpesa_c2b_confirmation_callback", args=[TOKEN]),
        data=json.dumps(payload),
        content_type="application/json",
    )


def create_subscriber_record(name="Phase 9.1 Subscriber") -> Subscriber:
    form = SubscriberForm(
        data={
            "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
            "display_name": name,
            "primary_phone": "0712 345 678",
            "email": "phase91@example.test",
            "reason": "Create subscriber",
        }
    )
    assert form.is_valid(), form.errors
    return create_subscriber(form=form, actor=None)


def create_role_user(username: str, role_name: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=role_name))
    return user


def sync_profile() -> PaymentProviderProfile:
    output = StringIO()
    call_command("sync_mpesa_paybill_profile", stdout=output)
    assert IDENTIFIER not in output.getvalue()
    return PaymentProviderProfile.objects.get(
        provider=PaymentProviderProfile.PROVIDER_MPESA,
        product_type=PaymentProviderProfile.PRODUCT_PAYBILL,
        environment=PaymentProviderProfile.ENVIRONMENT_SANDBOX,
    )


def imported_settings(env_updates: dict[str, str], *names: str):
    clean_keys = {
        "SUPERSURF_ENVIRONMENT",
        "SUPERSURF_PUBLIC_DEPLOYMENT",
        "DJANGO_DEBUG",
        "DJANGO_SECRET_KEY",
        "DATABASE_URL",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "MPESA_CALLBACK_TOKEN",
        "MPESA_PAYBILL_INGESTION_ENABLED",
        "MPESA_PAYBILL_EXTERNAL_IDENTIFIER",
    }
    env = os.environ.copy()
    for key in clean_keys:
        env.pop(key, None)
    env.update(env_updates)
    env["PYTHONPATH"] = str(Path.cwd())
    expression = ", ".join(repr(name) for name in names)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; import supersurf.settings as s; "
                f"names=[{expression}]; "
                "print(json.dumps({name: getattr(s, name) for name in names}))"
            ),
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


PUBLIC_LAB_ENV = {
    "SUPERSURF_ENVIRONMENT": "LAB",
    "SUPERSURF_PUBLIC_DEPLOYMENT": "true",
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "synthetic-lab-secret-value-for-settings-check-only",
    "DATABASE_URL": "postgresql://synthetic:synthetic@localhost:5432/synthetic",
    "DJANGO_ALLOWED_HOSTS": "sandbox.example.test",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://sandbox.example.test",
    "MPESA_CALLBACK_TOKEN": "0" * 64,
}


def test_paybill_ingestion_defaults_disabled():
    result = imported_settings({}, "MPESA_PAYBILL_INGESTION_ENABLED")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"MPESA_PAYBILL_INGESTION_ENABLED": False}


@pytest.mark.parametrize(
    "updates",
    [
        {"SUPERSURF_PUBLIC_DEPLOYMENT": "false"},
        {"SUPERSURF_ENVIRONMENT": "PRODUCTION"},
        {"MPESA_PAYBILL_EXTERNAL_IDENTIFIER": ""},
        {"MPESA_PAYBILL_EXTERNAL_IDENTIFIER": "not-a-paybill"},
        {"MPESA_PAYBILL_INGESTION_ENABLED": "maybe"},
    ],
)
def test_enabled_ingestion_fails_closed_for_unsupported_configuration(updates):
    env = PUBLIC_LAB_ENV | {
        "MPESA_PAYBILL_INGESTION_ENABLED": "true",
        "MPESA_PAYBILL_EXTERNAL_IDENTIFIER": IDENTIFIER,
    }
    env.update(updates)

    result = imported_settings(env, "MPESA_PAYBILL_INGESTION_ENABLED")

    assert result.returncode != 0
    assert IDENTIFIER not in result.stderr


def test_sandbox_preparation_preserves_paybill_settings_without_generation_or_output():
    script = Path("deploy/sandbox/prepare-environment.sh").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/deploy-sandbox.yml").read_text(encoding="utf-8")

    assert 'read_env_value MPESA_PAYBILL_INGESTION_ENABLED' in script
    assert 'read_env_value MPESA_PAYBILL_EXTERNAL_IDENTIFIER' in script
    assert "MPESA_PAYBILL_INGESTION_ENABLED=${mpesa_paybill_ingestion_enabled}" in script
    assert "MPESA_PAYBILL_EXTERNAL_IDENTIFIER=${mpesa_paybill_external_identifier}" in script
    assert 'mpesa_paybill_ingestion_enabled="false"' in script
    assert "openssl" not in "\n".join(
        line for line in script.splitlines() if "mpesa_paybill" in line.lower()
    )
    assert "echo ${mpesa_paybill" not in script
    assert "MPESA_PAYBILL_INGESTION_ENABLED=false" in workflow
    assert "MPESA_PAYBILL_EXTERNAL_IDENTIFIER=00000" in workflow


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_profile_sync_is_idempotent_sanitized_and_does_not_process_old_evidence():
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(),
    ).event

    first = sync_profile()
    second = sync_profile()

    assert first.pk == second.pk
    assert PaymentProviderProfile.objects.filter(provider="mpesa").count() == 1
    assert Payment.objects.count() == 0
    assert not MpesaCallbackPaymentLink.objects.filter(callback_event=event).exists()
    audit_text = str(list(AuditEvent.objects.values("safe_metadata", "reason")))
    assert IDENTIFIER not in audit_text
    assert AuditEvent.objects.filter(action="mpesa.paybill_profile_created").count() == 1


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_profile_sync_rejects_conflicting_active_profile_without_identity_output():
    PaymentProviderProfile.objects.create(
        name="Conflicting synthetic profile",
        provider=PaymentProviderProfile.PROVIDER_MPESA,
        product_type=PaymentProviderProfile.PRODUCT_PAYBILL,
        environment=PaymentProviderProfile.ENVIRONMENT_SANDBOX,
        external_identifier="654320",
        is_active=True,
    )
    output = StringIO()

    with pytest.raises(CommandError) as exc_info:
        call_command("sync_mpesa_paybill_profile", stdout=output, stderr=output)

    combined = output.getvalue() + str(exc_info.value)
    assert IDENTIFIER not in combined
    assert PaymentProviderProfile.objects.filter(provider="mpesa").count() == 1


@pytest.mark.django_db
@override_settings(MPESA_PAYBILL_INGESTION_ENABLED=False)
def test_disabled_profile_sync_creates_nothing():
    output = StringIO()

    call_command("sync_mpesa_paybill_profile", stdout=output)

    assert PaymentProviderProfile.objects.filter(provider="mpesa").count() == 0
    assert AuditEvent.objects.count() == 0
    assert "skipped" in output.getvalue().lower()


@pytest.mark.django_db
@override_settings(
    MPESA_CALLBACK_TOKEN=TOKEN,
    MPESA_PAYBILL_INGESTION_ENABLED=False,
    MPESA_PAYBILL_EXTERNAL_IDENTIFIER=IDENTIFIER,
)
def test_disabled_confirmation_remains_evidence_only(client):
    response = post_confirmation(client, c2b_payload())

    assert response.status_code == 200
    assert MpesaCallbackEvent.objects.count() == 1
    assert Payment.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_provider_identifier_extraction_is_normalized_blank_when_invalid_and_immutable():
    valid = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(TransID="P91IDENTIFIER1", BusinessShortCode=f" {IDENTIFIER} "),
    ).event
    invalid = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(TransID="P91IDENTIFIER2", BusinessShortCode="not-valid"),
    ).event

    assert valid.provider_external_identifier == IDENTIFIER
    assert invalid.provider_external_identifier == ""
    valid.provider_external_identifier = "654329"
    with pytest.raises(RuntimeError):
        valid.save()


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_missing_synchronized_profile_returns_safe_retryable_error(client):
    response = post_confirmation(client, c2b_payload())

    assert response.status_code == 500
    assert response.json() == {"error": "callback_processing_failed"}
    assert MpesaCallbackEvent.objects.count() == 1
    assert Payment.objects.count() == 0
    assert "profile_unavailable" in str(
        list(AuditEvent.objects.values("safe_metadata", "reason"))
    )


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        (MpesaCallbackEvent.EVENT_C2B_VALIDATION, c2b_payload()),
        (MpesaCallbackEvent.EVENT_STK_RESULT, {"ResultCode": 0, "BusinessShortCode": IDENTIFIER}),
        (
            MpesaCallbackEvent.EVENT_STK_RESULT,
            {"ResultCode": 1037, "BusinessShortCode": IDENTIFIER},
        ),
    ],
)
def test_validation_and_stk_events_are_evidence_only(client, event_type, payload):
    route = (
        "mpesa_c2b_validation_callback"
        if event_type == MpesaCallbackEvent.EVENT_C2B_VALIDATION
        else "mpesa_stk_callback"
    )
    response = client.post(
        reverse(route, args=[TOKEN]),
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert MpesaCallbackEvent.objects.count() == 1
    assert Payment.objects.count() == 0
    assert Wallet.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert PaymentAllocation.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_mismatched_provider_identifier_is_evidence_only(client):
    sync_profile()

    response = post_confirmation(client, c2b_payload(BusinessShortCode="654320"))

    assert response.status_code == 200
    assert Payment.objects.count() == 0
    assert MpesaCallbackPaymentLink.objects.count() == 0
    assert AuditEvent.objects.filter(reason="provider_identifier_mismatch").count() == 1


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
@pytest.mark.parametrize(
    ("provider", "product", "environment", "active"),
    [
        ("mpesa", "paybill", "sandbox", False),
        ("mpesa", "till", "sandbox", True),
        ("mpesa", "paybill", "test", True),
        ("fake", "fake", "test", True),
    ],
)
def test_wrong_or_inactive_profiles_are_rejected(provider, product, environment, active):
    PaymentProviderProfile.objects.create(
        name="Wrong synthetic profile",
        provider=provider,
        product_type=product,
        environment=environment,
        external_identifier=IDENTIFIER,
        is_active=active,
    )
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(),
    ).event

    with pytest.raises(PaybillProfileUnavailable):
        process_mpesa_paybill_confirmation_event(event)

    assert Payment.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
@pytest.mark.parametrize(
    "overrides",
    [
        {"TransID": None},
        {"TransAmount": None},
        {"TransAmount": "0"},
        {"TransAmount": "-1"},
        {"TransAmount": "NaN"},
        {"TransAmount": "Infinity"},
        {"TransAmount": "10000000000.00"},
        {"TransAmount": "1.001"},
    ],
)
def test_missing_or_invalid_financial_fields_are_evidence_only(client, overrides):
    sync_profile()

    response = post_confirmation(client, c2b_payload(**overrides))

    assert response.status_code == 200
    assert MpesaCallbackEvent.objects.count() == 1
    assert Payment.objects.count() == 0
    assert Wallet.objects.count() == 0
    assert MpesaCallbackPaymentLink.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_matched_confirmation_creates_one_system_credit_without_billing_side_effects(client):
    subscriber = create_subscriber_record()
    sync_profile()

    response = post_confirmation(
        client,
        c2b_payload(BillRefNumber=subscriber.account_number, TransAmount="1.00"),
    )

    assert response.status_code == 200
    payment = Payment.objects.get()
    allocation = PaymentAllocation.objects.select_related("ledger_entry", "wallet").get()
    link = MpesaCallbackPaymentLink.objects.get()
    assert payment.amount_minor == 100
    assert allocation.payment == payment
    assert allocation.amount_minor == 100
    assert allocation.creation_source == PaymentAllocation.SOURCE_SYSTEM
    assert allocation.created_by is None
    assert allocation.ledger_entry.entry_type == LedgerEntry.ENTRY_PAYMENT_CREDIT
    assert allocation.ledger_entry.creation_source == LedgerEntry.SOURCE_SYSTEM
    assert allocation.ledger_entry.created_by is None
    assert allocation.ledger_entry.balance_after_minor == 100
    assert allocation.wallet.balance_minor == 100
    assert link.payment == payment
    assert UnmatchedPaymentCase.objects.count() == 0
    assert BillingPeriod.objects.count() == 0
    assert BillingCharge.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
@pytest.mark.parametrize("reference", ["", "bad-ref", "SS999999", "SV000001"])
def test_unmatched_references_create_case_without_wallet_credit(client, reference):
    sync_profile()

    response = post_confirmation(
        client,
        c2b_payload(TransID=f"P91UNMATCHED{len(reference)}", BillRefNumber=reference),
    )

    assert response.status_code == 200
    assert Payment.objects.count() == 1
    case = UnmatchedPaymentCase.objects.get()
    assert case.status == UnmatchedPaymentCase.STATUS_OPEN
    assert MpesaCallbackPaymentLink.objects.count() == 1
    assert Wallet.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert PaymentAllocation.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_equivalent_duplicate_reuses_event_payment_link_credit_and_audit(client):
    subscriber = create_subscriber_record()
    sync_profile()
    payload = c2b_payload(BillRefNumber=subscriber.account_number)

    first = post_confirmation(client, payload)
    counts_after_first = {
        "events": MpesaCallbackEvent.objects.count(),
        "payments": Payment.objects.count(),
        "links": MpesaCallbackPaymentLink.objects.count(),
        "allocations": PaymentAllocation.objects.count(),
        "ledger": LedgerEntry.objects.count(),
        "cases": UnmatchedPaymentCase.objects.count(),
        "audit": AuditEvent.objects.count(),
    }
    balance_after_first = Wallet.objects.get().balance_minor
    second = post_confirmation(client, payload)

    assert first.status_code == second.status_code == 200
    assert counts_after_first == {
        "events": MpesaCallbackEvent.objects.count(),
        "payments": Payment.objects.count(),
        "links": MpesaCallbackPaymentLink.objects.count(),
        "allocations": PaymentAllocation.objects.count(),
        "ledger": LedgerEntry.objects.count(),
        "cases": UnmatchedPaymentCase.objects.count(),
        "audit": AuditEvent.objects.count(),
    }
    assert Wallet.objects.get().balance_minor == balance_after_first


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_conflicting_duplicate_preserves_original_and_never_credits_again(client):
    subscriber = create_subscriber_record()
    sync_profile()
    original = c2b_payload(BillRefNumber=subscriber.account_number, TransAmount="1.00")

    assert post_confirmation(client, original).status_code == 200
    event = MpesaCallbackEvent.objects.get()
    digest = event.payload_sha256
    assert post_confirmation(client, original | {"TransAmount": "2.00"}).status_code == 200

    event.refresh_from_db()
    assert event.payload_sha256 == digest
    assert Payment.objects.get().amount_minor == 100
    assert Wallet.objects.get().balance_minor == 100
    assert LedgerEntry.objects.count() == 1
    assert AuditEvent.objects.filter(reason="duplicate_payload_conflict").count() == 1


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_transient_processing_failure_retries_preserved_event_safely(client, monkeypatch):
    subscriber = create_subscriber_record()
    sync_profile()
    from billing import services

    attempts = 0

    def fail_once(event):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic transient failure")
        return services.process_mpesa_paybill_confirmation_event(event)

    monkeypatch.setattr("billing.views.process_mpesa_paybill_confirmation_event", fail_once)
    payload = c2b_payload(BillRefNumber=subscriber.account_number)

    first = post_confirmation(client, payload)
    second = post_confirmation(client, payload)

    assert first.status_code == 500
    assert first.json() == {"error": "callback_processing_failed"}
    assert second.status_code == 200
    assert MpesaCallbackEvent.objects.count() == 1
    assert Payment.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    assert Wallet.objects.get().balance_minor == 100


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_conflicting_existing_payment_is_not_mutated_or_allocated(client):
    profile = sync_profile()
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(),
    ).event
    payment = Payment.objects.create(
        provider_profile=profile,
        provider_transaction_id=event.provider_transaction_id,
        amount_minor=200,
        received_at=event.received_at,
        account_reference=event.account_reference,
        payload_digest=event.payload_sha256,
    )

    response = post_confirmation(client, c2b_payload())

    assert response.status_code == 500
    payment.refresh_from_db()
    assert payment.amount_minor == 200
    assert Payment.objects.count() == 1
    assert PaymentAllocation.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert MpesaCallbackPaymentLink.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_fake_payment_still_requires_operator_permissions():
    profile = PaymentProviderProfile.objects.create(
        name="Synthetic fake profile",
        provider="fake",
        product_type="fake",
        environment="test",
        external_identifier="synthetic-fake",
    )

    with pytest.raises(PermissionDenied):
        ingest_fake_payment(
            provider_profile=profile,
            provider_transaction_id="FAKE-P91",
            amount="1.00",
            received_at=timezone.now(),
            account_reference="",
            operation_id="de82551a-6a7c-48b7-b6e9-e68b4838ab45",
            actor=None,
        )


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_callback_payment_link_and_profile_identity_are_immutable(client):
    create_subscriber_record()
    profile = sync_profile()
    assert post_confirmation(client, c2b_payload()).status_code == 200
    link = MpesaCallbackPaymentLink.objects.get()

    with pytest.raises(RuntimeError):
        link.save(update_fields=["created_at"])
    with pytest.raises(RuntimeError):
        link.delete()
    with pytest.raises(RuntimeError):
        MpesaCallbackPaymentLink.objects.filter(pk=link.pk).update(payment=link.payment)
    with pytest.raises(RuntimeError):
        MpesaCallbackPaymentLink.objects.filter(pk=link.pk).delete()

    profile.external_identifier = "654329"
    with pytest.raises(RuntimeError):
        profile.save()
    profile.refresh_from_db()
    profile.is_active = False
    profile.save(update_fields=["is_active", "updated_at"])
    assert Payment.objects.filter(provider_profile=profile).count() == 1


@pytest.mark.django_db
def test_provider_profile_product_and_active_identity_constraints():
    with pytest.raises(ValidationError):
        PaymentProviderProfile.objects.create(
            name="Invalid pair",
            provider="fake",
            product_type="paybill",
            environment="test",
            external_identifier="synthetic-invalid",
        )

    PaymentProviderProfile.objects.create(
        name="First active sandbox Paybill",
        provider="mpesa",
        product_type="paybill",
        environment="sandbox",
        external_identifier="654320",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentProviderProfile.objects.bulk_create(
            [
                PaymentProviderProfile(
                    name="Second active sandbox Paybill",
                    provider="mpesa",
                    product_type="paybill",
                    environment="sandbox",
                    external_identifier="654329",
                )
            ]
        )


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_provenance_invariants_fail_at_model_and_database_levels(client, seeded_roles):
    subscriber = create_subscriber_record()
    sync_profile()
    assert post_confirmation(client, c2b_payload()).status_code == 200
    entry = LedgerEntry.objects.get()
    allocation = PaymentAllocation.objects.get()
    actor = create_role_user("provenance-admin", ROLE_ADMINISTRATOR)

    invalid = LedgerEntry(
        wallet=Wallet.objects.create(subscriber=create_subscriber_record("Other subscriber")),
        sequence_number=1,
        operation_id="05728d4c-b284-4b1f-ac39-8d10d463e921",
        entry_type=LedgerEntry.ENTRY_PAYMENT_CREDIT,
        direction=LedgerEntry.DIRECTION_CREDIT,
        amount_minor=100,
        balance_after_minor=100,
        reason="Invalid provenance",
        creation_source=LedgerEntry.SOURCE_SYSTEM,
        created_by=actor,
    )
    with pytest.raises(ValidationError):
        invalid.save()

    with pytest.raises(IntegrityError), transaction.atomic():
        LedgerEntry._base_manager.filter(pk=entry.pk).update(created_by=actor)
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentAllocation._base_manager.filter(pk=allocation.pk).update(created_by=actor)
    with pytest.raises(IntegrityError), transaction.atomic():
        LedgerEntry._base_manager.filter(pk=entry.pk).update(
            creation_source=LedgerEntry.SOURCE_OPERATOR,
            created_by=None,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentAllocation._base_manager.filter(pk=allocation.pk).update(
            creation_source=PaymentAllocation.SOURCE_OPERATOR,
            created_by=None,
        )

    allocation.creation_source = PaymentAllocation.SOURCE_OPERATOR
    allocation.created_by = None
    with pytest.raises(ValidationError):
        allocation.full_clean()

    allocation.refresh_from_db()
    assert entry.creation_source == LedgerEntry.SOURCE_SYSTEM
    assert allocation.creation_source == PaymentAllocation.SOURCE_SYSTEM
    assert subscriber.wallet.balance_minor == 100


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_roles_and_cross_links_respect_callback_permissions(client, seeded_roles):
    subscriber = create_subscriber_record()
    sync_profile()
    response = post_confirmation(
        client,
        c2b_payload(BillRefNumber=subscriber.account_number),
    )
    assert response.status_code == 200
    event = MpesaCallbackEvent.objects.get()
    payment = Payment.objects.get()
    link_permission = "billing.view_mpesacallbackpaymentlink"

    admin = create_role_user("p91-admin", ROLE_ADMINISTRATOR)
    finance = create_role_user("p91-finance", ROLE_FINANCE)
    support = create_role_user("p91-support", ROLE_SUPPORT)
    read_only = create_role_user("p91-readonly", ROLE_READ_ONLY)
    noc = create_role_user("p91-noc", ROLE_NOC)
    assert admin.has_perm(link_permission)
    assert finance.has_perm(link_permission)
    assert not support.has_perm("billing.view_mpesacallbackevent")
    assert not read_only.has_perm("billing.view_mpesacallbackevent")
    assert not noc.has_perm("billing.view_mpesacallbackevent")

    client.force_login(admin)
    callback_response = client.get(reverse("mpesa_callback_event_detail", args=[event.pk]))
    payment_response = client.get(reverse("payment_detail", args=[payment.pk]))
    wallet_response = client.get(reverse("wallet_detail", args=[subscriber.pk]))
    assert "Linked" in callback_response.content.decode()
    assert "View canonical payment" in callback_response.content.decode()
    assert "Source callback" in payment_response.content.decode()
    assert "System" in payment_response.content.decode()
    assert "System" in wallet_response.content.decode()

    client.force_login(support)
    assert client.get(reverse("mpesa_callback_event_detail", args=[event.pk])).status_code == 403
    support_payment = client.get(reverse("payment_detail", args=[payment.pk]))
    assert support_payment.status_code == 200
    assert "Source callback" not in support_payment.content.decode()
    assert str(event.pk) not in support_payment.content.decode()


@pytest.mark.django_db
@override_settings(**ENABLED_SETTINGS)
def test_logs_and_audits_exclude_callback_secrets_and_provider_values(client, caplog):
    create_subscriber_record()
    sync_profile()
    payload = c2b_payload(
        MSISDN="254799999999",
        FirstName="SensitiveName",
        OrgAccountBalance="123456.00",
    )

    with caplog.at_level("INFO"):
        response = post_confirmation(client, payload)

    assert response.status_code == 200
    audit_text = str(list(AuditEvent.objects.values("safe_metadata", "reason")))
    combined = caplog.text + audit_text
    for forbidden in [
        TOKEN,
        IDENTIFIER,
        "254799999999",
        "SensitiveName",
        "123456.00",
        "/api/payment-callbacks/",
    ]:
        assert forbidden not in combined


@pytest.mark.django_db(transaction=True)
@override_settings(**ENABLED_SETTINGS)
def test_concurrent_duplicate_confirmation_is_safe_on_postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL locking test")
    subscriber = create_subscriber_record()
    sync_profile()
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_CONFIRMATION,
        c2b_payload(BillRefNumber=subscriber.account_number),
    ).event
    barrier = Barrier(2)

    def process_once():
        close_old_connections()
        try:
            barrier.wait()
            local_event = MpesaCallbackEvent.objects.get(pk=event.pk)
            return process_mpesa_paybill_confirmation_event(local_event).outcome
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: process_once(), range(2)))

    assert sorted(outcomes) == ["already_processed", "processed"]
    assert Payment.objects.count() == 1
    assert MpesaCallbackPaymentLink.objects.count() == 1
    assert PaymentAllocation.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    assert Wallet.objects.get().balance_minor == 100
