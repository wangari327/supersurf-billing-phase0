from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from threading import Barrier

import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db import IntegrityError, close_old_connections, connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from audit.logging import redact_text
from billing.models import (
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    MpesaCallbackEvent,
    Payment,
    Wallet,
)
from billing.mpesa_callbacks import REDACTED, capture_mpesa_callback, payload_digest
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

TOKEN = "a" * 64
BASE_URL = "https://sandbox-api.supersurf.co.ke"


def c2b_payload(**overrides):
    payload = {
        "TransID": "P9C2B12345",
        "TransAmount": "1200.00",
        "BillRefNumber": "SS000001",
        "MSISDN": "254712345678",
        "FirstName": "Alice",
        "MiddleName": "Example",
        "LastName": "Subscriber",
        "OrgAccountBalance": "99999.00",
    }
    payload.update(overrides)
    return payload


def stk_payload(result_code=0, **overrides):
    callback = {
        "MerchantRequestID": "29115-34620561-1",
        "CheckoutRequestID": "ws_CO_010220261030001234567890",
        "ResultCode": result_code,
        "ResultDesc": "The service request is processed successfully."
        if result_code == 0
        else "DS timeout user cannot be reached",
        "CallbackMetadata": {
            "Item": [
                {"Name": "Amount", "Value": 1500},
                {"Name": "MpesaReceiptNumber", "Value": "P9STK12345"},
                {"Name": "PhoneNumber", "Value": 254712345678},
            ]
        },
    }
    callback.update(overrides)
    return {"Body": {"stkCallback": callback}}


def post_json(client, url_name: str, payload, token: str = TOKEN):
    return client.post(
        reverse(url_name, args=[token]),
        data=json.dumps(payload),
        content_type="application/json",
    )


def create_staff_with_role(username: str, role_name: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="StrongStaffPass123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name=role_name))
    return user


def create_test_subscriber() -> Subscriber:
    form = SubscriberForm(
        data={
            "customer_type": Subscriber.CUSTOMER_INDIVIDUAL,
            "display_name": "Phase Nine Subscriber",
            "primary_phone": "0712 345 678",
            "email": "phase9@example.test",
            "reason": "Create subscriber",
        }
    )
    assert form.is_valid(), form.errors
    return create_subscriber(form=form, actor=None)


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_correct_callback_token_accepted(client):
    response = post_json(client, "mpesa_c2b_validation_callback", c2b_payload())

    assert response.status_code == 200
    assert response.json() == {"ResultCode": 0, "ResultDesc": "Accepted"}
    assert MpesaCallbackEvent.objects.count() == 1


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_incorrect_callback_token_returns_404(client):
    response = post_json(client, "mpesa_c2b_validation_callback", c2b_payload(), token="wrong")

    assert response.status_code == 404
    assert response["content-type"].startswith("application/json")
    assert MpesaCallbackEvent.objects.count() == 0


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_missing_token_route_returns_404(client):
    response = client.post(
        reverse("mpesa_c2b_validation_missing_token"),
        data=json.dumps(c2b_payload()),
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_get_callback_returns_405(client):
    response = client.get(reverse("mpesa_c2b_validation_callback", args=[TOKEN]))

    assert response.status_code == 405
    assert response["Allow"] == "POST"
    assert response["content-type"].startswith("application/json")


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_malformed_json_returns_400(client):
    response = client.post(
        reverse("mpesa_c2b_validation_callback", args=[TOKEN]),
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response["content-type"].startswith("application/json")


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_nonstandard_json_constants_return_400(client):
    response = client.post(
        reverse("mpesa_c2b_validation_callback", args=[TOKEN]),
        data='{"TransAmount": NaN}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert MpesaCallbackEvent.objects.count() == 0


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_oversized_request_returns_413(client):
    response = client.post(
        reverse("mpesa_c2b_validation_callback", args=[TOKEN]),
        data=b"{" + (b" " * (64 * 1024)) + b"}",
        content_type="application/json",
    )

    assert response.status_code == 413


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_c2b_validation_capture(client):
    payload = c2b_payload(TransID="P9VALIDATE")

    response = post_json(client, "mpesa_c2b_validation_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    assert response.status_code == 200
    assert event.event_type == MpesaCallbackEvent.EVENT_C2B_VALIDATION
    assert event.provider_transaction_id == "P9VALIDATE"
    assert event.account_reference == "SS000001"
    assert event.amount == Decimal("1200.00")
    assert event.payload_sha256 == payload_digest(payload)


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_c2b_confirmation_capture(client):
    payload = c2b_payload(TransID="P9CONFIRM")

    response = post_json(client, "mpesa_c2b_confirmation_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    assert response.status_code == 200
    assert event.event_type == MpesaCallbackEvent.EVENT_C2B_CONFIRMATION
    assert event.provider_transaction_id == "P9CONFIRM"


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_successful_stk_result_capture(client):
    payload = stk_payload()

    response = post_json(client, "mpesa_stk_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    assert response.status_code == 200
    assert event.event_type == MpesaCallbackEvent.EVENT_STK_RESULT
    assert event.provider_transaction_id == "P9STK12345"
    assert event.merchant_request_id == "29115-34620561-1"
    assert event.checkout_request_id == "ws_CO_010220261030001234567890"
    assert event.amount == Decimal("1500.00")
    assert event.result_code == "0"
    assert event.result_description == "The service request is processed successfully."


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_failed_stk_result_1037_capture_without_payment_side_effects(client):
    payload = stk_payload(result_code=1037)

    response = post_json(client, "mpesa_stk_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    assert response.status_code == 200
    assert event.result_code == "1037"
    assert Payment.objects.count() == 0
    assert Wallet.objects.count() == 0
    assert LedgerEntry.objects.count() == 0


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_nested_callback_metadata_extraction_and_recursive_redaction(client):
    payload = stk_payload()

    post_json(client, "mpesa_stk_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    metadata_items = event.sanitized_payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
    phone_item = next(item for item in metadata_items if item["Name"] == "PhoneNumber")
    assert event.provider_transaction_id == "P9STK12345"
    assert phone_item["Value"] == REDACTED


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_invalid_normalized_fields_do_not_prevent_evidence_capture(client):
    payload = c2b_payload(
        TransID="T" * 129,
        TransAmount="Infinity",
        BillRefNumber="R" * 65,
        ResultCode="9" * 17,
        ResultDesc="D" * 241,
    )

    response = post_json(client, "mpesa_c2b_validation_callback", payload)
    event = MpesaCallbackEvent.objects.get()

    assert response.status_code == 200
    assert event.provider_transaction_id == ""
    assert event.account_reference == ""
    assert event.amount is None
    assert event.result_code == ""
    assert event.result_description == "D" * 240
    assert event.idempotency_key == f"c2b_validation:sha256:{event.payload_sha256}"


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_sensitive_fields_are_redacted_and_raw_body_is_not_persisted(client):
    payload = c2b_payload(
        Password="secret-password",
        Authorization="Bearer secret-token",
        Nested={"phone_number": "254700000000", "safe": "kept"},
    )
    raw_body = json.dumps(payload)

    client.post(
        reverse("mpesa_c2b_validation_callback", args=[TOKEN]),
        data=raw_body,
        content_type="application/json",
    )
    event = MpesaCallbackEvent.objects.get()
    stored = json.dumps(event.sanitized_payload, sort_keys=True)

    assert "254712345678" not in stored
    assert "Alice" not in stored
    assert "Subscriber" not in stored
    assert "99999.00" not in stored
    assert "secret-password" not in stored
    assert "secret-token" not in stored
    assert "254700000000" not in stored
    assert event.sanitized_payload["TransID"] == payload["TransID"]
    assert event.sanitized_payload["Nested"]["safe"] == "kept"
    assert not hasattr(event, "raw_body")


def test_deterministic_canonical_hashing():
    left = {"b": [2, {"d": 4}], "a": 1}
    right = {"a": 1, "b": [2, {"d": 4}]}

    assert payload_digest(left) == payload_digest(right)


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_no_sensitive_values_in_captured_logs(client, caplog):
    payload = c2b_payload(TransID="P9LOGSAFE", MSISDN="254799999999", FirstName="LogName")

    with caplog.at_level("INFO", logger="billing.mpesa_callbacks"):
        post_json(client, "mpesa_c2b_validation_callback", payload)

    assert "P9LOGSAFE" not in caplog.text
    assert "254799999999" not in caplog.text
    assert "LogName" not in caplog.text
    assert TOKEN not in caplog.text
    assert "mpesa_callback_event" in caplog.text


@pytest.mark.parametrize(
    "suffix",
    ["c2b/validation/", "c2b/confirmation/", "stk/callback/"],
)
def test_framework_log_redaction_masks_callback_url_token(suffix):
    message = f"Request failed: /api/integrations/mpesa/{TOKEN}/{suffix}"

    redacted = redact_text(message)

    assert TOKEN not in redacted
    assert f"/api/integrations/mpesa/[redacted]/{suffix}" in redacted


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_duplicate_callbacks_create_one_row(client):
    payload = c2b_payload(TransID="P9DUPLICATE")

    first = post_json(client, "mpesa_c2b_validation_callback", payload)
    second = post_json(client, "mpesa_c2b_validation_callback", payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert MpesaCallbackEvent.objects.count() == 1


@pytest.mark.django_db
def test_database_uniqueness_enforces_idempotency_key():
    payload = c2b_payload(TransID="P9DBUNIQUE")
    captured = capture_mpesa_callback(MpesaCallbackEvent.EVENT_C2B_VALIDATION, payload)

    with pytest.raises(IntegrityError):
        MpesaCallbackEvent.objects.bulk_create(
            [
                MpesaCallbackEvent(
                    event_type=MpesaCallbackEvent.EVENT_C2B_VALIDATION,
                    payload_sha256=captured.event.payload_sha256,
                    idempotency_key=captured.event.idempotency_key,
                    sanitized_payload={},
                )
            ]
        )


@pytest.mark.django_db
def test_model_update_and_deletion_are_prevented():
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_VALIDATION,
        c2b_payload(TransID="P9IMMUTABLE"),
    ).event
    original_created_at = event.created_at

    event.result_code = "99"
    with pytest.raises(RuntimeError):
        event.save()
    event.refresh_from_db()
    event.created_at = timezone.now() + timedelta(days=1)
    with pytest.raises(RuntimeError):
        event.save(update_fields=["created_at"])
    event.refresh_from_db()
    assert event.created_at == original_created_at
    with pytest.raises(RuntimeError):
        MpesaCallbackEvent.objects.filter(pk=event.pk).update(result_code="99")
    with pytest.raises(RuntimeError):
        MpesaCallbackEvent.objects.bulk_update([event], ["result_code"])
    with pytest.raises(RuntimeError):
        event.delete()
    with pytest.raises(RuntimeError):
        MpesaCallbackEvent.objects.filter(pk=event.pk).delete()


@pytest.mark.django_db
def test_read_only_operator_permissions(client, seeded_roles):
    event = capture_mpesa_callback(
        MpesaCallbackEvent.EVENT_C2B_VALIDATION,
        c2b_payload(TransID="P9VISIBLE", MSISDN="254711111111"),
    ).event
    finance = create_staff_with_role("phase9-finance", ROLE_FINANCE)
    support = create_staff_with_role("phase9-support", ROLE_SUPPORT)

    client.force_login(finance)
    list_response = client.get(reverse("mpesa_callback_event_list"))
    detail_response = client.get(reverse("mpesa_callback_event_detail", args=[event.pk]))
    detail_html = detail_response.content.decode()
    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert "P9VISIBLE" in detail_html
    assert "254711111111" not in detail_html
    assert TOKEN not in detail_html

    client.force_login(support)
    assert client.get(reverse("mpesa_callback_event_list")).status_code == 403


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN)
def test_successful_callback_does_not_create_payment_wallet_billing_or_renewal(
    client,
    seeded_roles,
):
    subscriber = create_test_subscriber()
    form = ServiceForm(data={"label": "Phase 9 service", "reason": "Create service"})
    assert form.is_valid(), form.errors
    service = create_service(subscriber=subscriber, form=form, actor=None)

    response = post_json(client, "mpesa_stk_callback", stk_payload())

    assert response.status_code == 200
    assert Payment.objects.count() == 0
    assert Wallet.objects.count() == 0
    assert LedgerEntry.objects.count() == 0
    assert BillingPeriod.objects.count() == 0
    assert BillingCharge.objects.count() == 0
    service.refresh_from_db()
    assert service.subscriber_id == subscriber.pk


@pytest.mark.django_db
@override_settings(MPESA_CALLBACK_TOKEN=TOKEN, MPESA_CALLBACK_BASE_URL=BASE_URL)
def test_callback_url_command_outputs_urls_and_missing_token_fails():
    output = StringIO()

    call_command("show_mpesa_callback_urls", stdout=output)

    text = output.getvalue()
    assert f"{BASE_URL}/api/integrations/mpesa/{TOKEN}/c2b/validation/" in text
    assert f"{BASE_URL}/api/integrations/mpesa/{TOKEN}/c2b/confirmation/" in text
    assert f"{BASE_URL}/api/integrations/mpesa/{TOKEN}/stk/callback/" in text
    assert "consumer" not in text.lower()
    with override_settings(MPESA_CALLBACK_TOKEN=""):
        with pytest.raises(CommandError):
            call_command("show_mpesa_callback_urls", stdout=StringIO())


@pytest.mark.django_db
def test_seed_roles_assigns_callback_permission_to_finance_and_admin_only(seeded_roles):
    call_command("seed_roles", verbosity=0)

    def permissions(role_name: str):
        return set(
            Group.objects.get(name=role_name).permissions.values_list(
                "content_type__app_label",
                "codename",
            )
        )

    admin_permissions = permissions(ROLE_ADMINISTRATOR)
    finance_permissions = permissions(ROLE_FINANCE)
    support_permissions = permissions(ROLE_SUPPORT)
    read_only_permissions = permissions(ROLE_READ_ONLY)
    noc_permissions = permissions(ROLE_NOC)

    assert ("billing", "view_mpesacallbackevent") in admin_permissions
    assert ("billing", "view_mpesacallbackevent") in finance_permissions
    assert ("billing", "view_mpesacallbackevent") not in support_permissions
    assert ("billing", "view_mpesacallbackevent") not in read_only_permissions
    assert ("billing", "view_mpesacallbackevent") not in noc_permissions
    assert ("billing", "add_mpesacallbackevent") not in admin_permissions
    assert ("billing", "change_mpesacallbackevent") not in admin_permissions
    assert ("billing", "delete_mpesacallbackevent") not in admin_permissions


def test_sandbox_environment_generation_preserves_existing_mpesa_callback_token():
    script = (Path.cwd() / "deploy" / "sandbox" / "prepare-environment.sh").read_text()

    assert 'mpesa_callback_token="$(read_env_value MPESA_CALLBACK_TOKEN)"' in script
    assert 'if [ -z "${mpesa_callback_token}" ]; then' in script
    assert 'mpesa_callback_token="$(openssl rand -hex 32)"' in script
    assert "MPESA_CALLBACK_TOKEN=${mpesa_callback_token}" in script


@pytest.mark.django_db(transaction=True)
def test_concurrent_postgresql_duplicate_callbacks_create_one_event():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL duplicate callback concurrency is verified in CI.")
    barrier = Barrier(2)
    payload = c2b_payload(TransID="P9CONCURRENT")

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            captured = capture_mpesa_callback(
                MpesaCallbackEvent.EVENT_C2B_VALIDATION,
                payload,
            )
            return str(captured.event.pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in [executor.submit(worker), executor.submit(worker)]]

    assert len(set(results)) == 1
    assert MpesaCallbackEvent.objects.count() == 1
