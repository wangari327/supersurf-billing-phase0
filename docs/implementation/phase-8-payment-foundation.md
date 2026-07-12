# Phase 8 Payment Foundation

Phase 8 adds provider-neutral payment records, account-reference matching, Wallet credits, and an unmatched-payment workflow.

This phase uses only a fake payment provider for development and tests. It does not make Safaricom or Daraja calls, implement M-PESA callbacks, store Paybill or Till credentials, start STK Push, import reconciliation statements, issue invoices or receipts, create discounts, automatically spend Wallet credit, automatically renew services, suspend service, provision network access, write FreeRADIUS rows, create PPPoE credentials, call RouterOS, or perform live network actions.

Phase 9 may connect a thin M-PESA adapter to the canonical payment service once Daraja sandbox evidence and provider-specific controls are reviewed.

## Data Model

`billing.PaymentProviderProfile` stores a provider, product type, environment, external identifier, active flag, and timestamps. Phase 8 supports structural `mpesa` profiles, but only active `fake` profiles with `test` or `sandbox` environment can ingest payments. No credentials, tokens, certificates, callback secrets, or raw provider configuration belong in this model.

`billing.Payment` stores one canonical provider transaction:

- UUID primary key
- protected provider-profile foreign key
- provider transaction identifier
- positive integer KES minor-unit amount
- fixed `KES` currency
- aware received timestamp
- optional normalized account reference, limited to 64 characters
- optional SHA-256 payload digest
- creation timestamp

`Payment` records are immutable and append-only in application code, including their creation timestamps. The payment state is derived from allocations: no allocation means unmatched; one full allocation means allocated.

`billing.PaymentAllocation` links one full payment amount to one subscriber Wallet in Phase 8:

- UUID primary key
- protected payment foreign key
- protected wallet foreign key
- ledger-entry one-to-one link
- unique operation ID
- fixed allocation type `wallet_credit`
- positive integer KES minor-unit amount
- fixed `KES` currency
- protected creating operator foreign key
- creation timestamp

`PaymentAllocation` records are immutable and append-only in application code. Phase 8 permits only one full Wallet allocation per payment so later controlled split allocation can be added without replacing the canonical payment model.

`billing.UnmatchedPaymentCase` opens when a valid payment cannot be matched safely to a subscriber account reference. Open cases have no resolution fields. Resolved cases require the selected Wallet, resolution allocation, operator, reason, and resolved timestamp. Cases cannot be deleted or reopened through ordinary workflows.

The ledger has a new `payment_credit` entry type. It is always a credit, cannot reverse another ledger entry, cannot be posted through the manual adjustment service, cannot be reversed through the manual reversal workflow, and must be linked to a `PaymentAllocation`.

## Account Matching

Phase 8 account references are normalized by trimming surrounding whitespace and converting to uppercase.

A valid account reference is exactly `SS` followed by six digits, such as `SS000001`. Lowercase and whitespace-wrapped inputs normalize to the same value.

When the normalized reference matches a `Subscriber.account_number`, the full payment amount is credited to that subscriber's account-level Wallet. If the subscriber has no Wallet, one is created lazily inside the same transaction.

When the reference is missing, malformed, a service reference such as `SS000001-01`, or not found, the payment remains valid and an open `UnmatchedPaymentCase` is created. No Wallet, ledger entry, or allocation is created for unmatched intake.

Matching never uses subscriber names, email addresses, phone numbers, partial account numbers, service references, or fuzzy text.

## Services

`ingest_fake_payment` creates or locates the canonical `Payment`, verifies fake-provider scope, applies idempotency checks, matches the account reference, and either credits a Wallet or opens an unmatched case.

`resolve_unmatched_payment` lets an Administrator or Finance operator explicitly select a subscriber for an open case. It allocates the full payment amount to that subscriber Wallet, creates a `payment_credit` ledger entry, creates a `PaymentAllocation`, marks the case resolved, and records audit events atomically.

Both services run inside `transaction.atomic()` and use operation IDs to reject conflicts with existing ledger entries, payment allocations, billing periods, and billing charges. Equivalent provider retries return the original payment without creating another Wallet, allocation, ledger entry, unmatched case, or audit event.

Matched ingestion locks in this order:

1. provider profile
2. canonical payment
3. subscriber
4. Wallet
5. latest ledger entry
6. allocation and ledger credit
7. audit events

Unmatched resolution locks in this order:

1. payment and unmatched case
2. selected subscriber
3. Wallet
4. latest ledger entry
5. allocation and ledger credit
6. case resolution
7. audit events

PostgreSQL CI is authoritative for duplicate provider callbacks, ledger sequence preservation, concurrent first Wallet creation, and concurrent unmatched resolution behavior. SQLite local tests skip only PostgreSQL row-lock cases.

## Permissions

Administrator and Finance can ingest fake payments and resolve unmatched cases through the service layer. They receive the payment and unmatched-case add/change permissions required for those workflows.

SuperSurf Support and Read Only can view payment, allocation, and unmatched-case records. They cannot ingest fake payments, resolve unmatched cases, mutate payments, or mutate allocations.

NOC receives no payment, allocation, or unmatched-payment permissions.

No ordinary role receives delete permissions for payments, allocations, or unmatched cases. Ordinary roles also do not receive change permissions for `Payment` or `PaymentAllocation`.

## Operator UI

Phase 8 adds:

- `/payments/`
- `/payments/fake/new/`
- `/payments/<uuid:pk>/`
- `/payments/unmatched/`
- `/payments/unmatched/<uuid:pk>/resolve/`

The fake-payment form is visible only outside production and warns that it is not M-PESA. Payment lists can filter by allocated or unmatched state, provider profile, and date, and can search provider transaction IDs, account references, and subscriber account numbers.

Payment details show amount, provider, reference, received time, allocation, and unmatched-case state. Unmatched resolution requires selecting a subscriber explicitly and entering a reason.

Operation IDs and raw callback payloads are not displayed. Subscriber Wallet history displays payment credits and provider transaction IDs only to users with payment visibility.

## Audit

Successful workflows may record:

- `payment.received`
- `payment.allocated`
- `payment.unmatched`
- `payment.unmatched_resolved`
- `wallet.payment_credit`

Audit metadata is limited to generated identifiers, provider profile details, provider transaction IDs, matched account numbers, Wallet and allocation identifiers, ledger-entry identifiers, integer amounts, resulting balances, currency, received timestamps, normalized account references that match the account format, and unmatched reason codes.

Audit metadata must not store operation IDs, raw request payloads, full phone numbers, email addresses, subscriber display names, credentials, tokens, callback secrets, CSRF tokens, or card or bank credentials.

## Admin

Payment, PaymentAllocation, and UnmatchedPaymentCase admin pages are read-only. PaymentProviderProfile is also read-only in Django admin for this phase; the default fake test profile is seeded by migration and contains no secrets.

## Boundaries And Risks

Application code rejects model save changes, queryset updates, bulk updates, model deletion, and queryset deletion for immutable payment records. These are application-level controls only. Privileged direct database writes or compromised database credentials remain outside this protection.

Matched payments credit the account-level Wallet only. Partial and overpayments remain Wallet credit. Service renewal remains a separate operator action, and automatic Wallet spending is not implemented in Phase 8.
