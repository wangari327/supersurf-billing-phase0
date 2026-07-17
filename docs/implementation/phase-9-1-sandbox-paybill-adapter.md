# Phase 9.1 Sandbox Paybill Canonical Payment Adapter

Phase 9.1 is the Owner-approved bridge from immutable Phase 9 evidence to the Phase 8 canonical payment service. It processes only inbound M-PESA sandbox Paybill `c2b_confirmation` events in a public LAB deployment. No outbound Daraja request is made.

## Configuration

The feature is fail-closed and disabled by default:

```text
MPESA_PAYBILL_INGESTION_ENABLED=false
MPESA_PAYBILL_EXTERNAL_IDENTIFIER=
```

Enabling requires `SUPERSURF_ENVIRONMENT=LAB`, `SUPERSURF_PUBLIC_DEPLOYMENT=true`, an explicit true enable flag, a 5-12 digit external identifier, and an `MPESA_CALLBACK_TOKEN` of at least 32 characters. Production, private LAB, missing identifiers, malformed identifiers, and unsupported boolean values fail during Django settings import. The external identifier is financial routing configuration, not a credential, but its configured value is never printed or logged.

`deploy/sandbox/prepare-environment.sh` preserves both values in the mode-600 environment file. It defaults them to false and empty, never generates them, and never prints them.

## Provider Profile Sync

After migrations and role seeding, sandbox deployment runs:

```bash
python manage.py sync_mpesa_paybill_profile
```

When disabled, the command is a no-op. When enabled, it creates or activates one generic `M-PESA Sandbox Paybill` profile from Django settings. It is idempotent, never accepts the identifier as a command-line argument, never prints it, records a sanitized create/activate audit event, and fails if another active sandbox Paybill profile would silently switch financial identity. It does not process historical callback events.

Provider-profile constraints require fake/fake and M-PESA/Paybill-or-Till product pairs and permit only one active M-PESA profile per product and environment. Provider, product, environment, and external identifier cannot change through model save after payments exist. Deactivation does not mutate historical payments.

## Callback Decision Table

| Event or state | Result |
| --- | --- |
| Ingestion disabled | Evidence only; HTTP 200 acknowledgement |
| C2B validation | Evidence only; HTTP 200 acknowledgement |
| STK result, including `0` and `1037` | Evidence only; HTTP 200 acknowledgement |
| Confirmation with missing transaction or valid amount | Evidence retained; bounded skip reason; HTTP 200 |
| Confirmation with mismatched provider identifier | Evidence retained; bounded skip reason; HTTP 200 |
| Enabled confirmation with missing synchronized profile | Evidence retained; safe HTTP 500 for retry |
| Valid matched confirmation | Canonical Payment, Wallet credit, ledger entry, allocation, and evidence link; HTTP 200 |
| Valid unmatched confirmation | Canonical Payment, open unmatched case, and evidence link; HTTP 200 |
| Equivalent retry | Existing event, Payment, and link; HTTP 200 with no duplicate accounting or audit |
| Same idempotency key with changed payload | Original event preserved; no processing; sanitized conflict audit; HTTP 200 |

## Canonical Flow

Capture first writes the immutable `MpesaCallbackEvent`, including a normalized `provider_external_identifier` extracted only from `BusinessShortCode`. Processing rereads and locks that event; request JSON is not passed to the financial service.

The dedicated internal processor verifies the public LAB gate, event type, provider transaction ID, positive finite amount, exact configured identifier, and active M-PESA Paybill sandbox profile. Decimal KSh converts exactly to integer minor units. A deterministic UUID derived from the callback event drives ledger/allocation idempotency.

The private provider-neutral core retains the Phase 8 account-reference behavior. `SS000001`-style references credit the matching subscriber's account Wallet. Missing, malformed, service-reference, and unknown references create an open `UnmatchedPaymentCase` and no Wallet credit. Payment, allocation, ledger/unmatched case, and `MpesaCallbackPaymentLink` creation share one transaction.

Existing Payments are reused only when amount, currency, received time, normalized reference, and immutable callback digest match. Conflicts are never overwritten or reallocated.

## Provenance And Immutability

`LedgerEntry` and `PaymentAllocation` have immutable `operator` or `system` creation sources. Existing rows migrate as `operator`. Operator rows require `created_by`; system rows require it to be null. Database constraints enforce both combinations, and allocation provenance must match its ledger entry. The system path is limited to sandbox M-PESA Paybill payment credits. Operator pages display `System` instead of creating a fake user.

`MpesaCallbackPaymentLink` is one-to-one with both callback event and Payment. It uses protected foreign keys and rejects instance, queryset, bulk-update, and delete paths. Validation requires a C2B confirmation and matching provider profile, transaction, amount, normalized reference, and payload digest. Existing callback events remain unlinked.

## Failure And Security Handling

Provider acknowledgements and HTTP 500 responses contain no token, URL, identifier, payload, or exception detail. Logs and audit events use internal UUIDs and bounded outcome codes only. They exclude callback JSON, configured external identifiers, shortcodes, telephone numbers, names, provider balances, credentials, request headers, cookies, sessions, and client addresses.

The callback event survives a transactional processing failure, so an equivalent provider retry can safely retry processing. Conflicting duplicate payloads never mutate the original evidence or credit again. PostgreSQL row locks and unique constraints serialize concurrent equivalent processing.

## Permissions

Callback and link records remain read-only. Owner has all permissions. Administrator and Finance receive `billing.view_mpesacallbackevent` and `billing.view_mpesacallbackpaymentlink`. Support, Read Only, and NOC receive neither callback permission. Callback detail links to a Payment only with `billing.view_payment`; Payment detail reveals its source callback only with `billing.view_mpesacallbackevent`.

## Disable And Rollback

Set `MPESA_PAYBILL_INGESTION_ENABLED=false`, preserve the identifier privately, and redeploy. Evidence capture and acknowledgements continue, but no new callback creates a Payment. Existing Payments, Wallet entries, allocations, unmatched cases, and links remain immutable. Rolling back application code does not require deleting financial history.

## Strict Exclusions

Phase 9.1 does not enable Till, production M-PESA, STK-to-payment processing, Daraja authentication, outbound calls, transaction status, Pull Transactions, statements, reconciliation, reversal, refund, invoice, receipt, Wallet spending, activation, renewal, billing-period or billing-charge creation, suspension, notification, RADIUS, PPPoE, RouterOS, provisioning, background processing, or customer-facing payments. Phase 9.2 is not approved.

## Remaining Manual Verification

- [ ] After Owner deployment and configuration, perform one controlled sandbox Paybill payment and verify one confirmation-to-Payment link and either one exact Wallet credit or one expected unmatched case.

This live Phase 9.1 payment test remains pending. Automated tests and the earlier Phase 9 evidence run do not complete it.
