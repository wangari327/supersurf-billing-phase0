# M-PESA Payment Workflows

## Scope

Initial M-PESA support should focus on safely recording and allocating incoming Paybill and Till payments. Customer-facing STK Push is not required for the internal MVP.

Do not use production credentials in development.

Do not implement a mobile-money aggregator. SuperSurf Billing should integrate only with SuperSurf's configured Daraja products.

No M-PESA implementation may begin until authenticated product documentation and sandbox evidence are collected in `docs/research/mpesa-sandbox-evidence-checklist.md`.

## Explicit Daraja Uncertainty

The public Daraja catalogue is not sufficient to implement the production callback contract by assumption. Implementation must not assume:

- Callbacks are cryptographically signed.
- Safaricom callback source IPs are fixed.
- Source-IP allowlisting is sufficient authentication.
- Paybill and Till callbacks have identical structures.
- Till always provides payer MSISDN.
- Till always provides an account reference.
- Every product supports validation and confirmation identically.
- Transaction query is enabled for every product.

## Provider Profiles

Each M-PESA product must be represented by a `PaymentProviderProfile` or `MpesaProviderProfile` with:

- Product type: Paybill or Till
- Environment: sandbox or production
- Shortcode or Till identifier
- Enabled state
- Credential reference
- Callback configuration
- Reconciliation configuration

Credentials must be encrypted or referenced through a secret provider. They must not be stored in ordinary profile display fields.

## Shared Workflow

1. Receive callback over HTTPS.
2. Validate request source, URL, method, acknowledgement contract, and payload shape against sandbox evidence for the configured provider profile.
3. Persist the raw `WebhookEvent` with secret redaction.
4. Determine whether the event represents a valid financial transaction.
5. For every valid provider transaction, create or locate one canonical `Payment`.
6. Enforce idempotency using provider profile, environment, and provider transaction identifier.
7. Normalize amount into integer minor units.
8. Normalize payer phone if present and verified for the product.
9. Match payment according to Paybill or Till rules.
10. Create zero or more `PaymentAllocation` records.
11. Open an optional `UnmatchedPaymentCase` when no safe allocation exists.
12. Apply renewal logic only through allocation, ledger, and subscription services in later phases.
13. Create audit events for allocation, manual resolution, reversal, and rejection.
14. Expose reconciliation status.

## Payment Lifecycle

Payment lifecycle values should include:

- `received`
- `unmatched`
- `partially_allocated`
- `allocated`
- `reversed`
- `refunded_externally`
- `rejected` only when no valid financial transaction exists

## Allocations

`PaymentAllocation` must support:

- Payment
- Subscriber or wallet
- Invoice or renewal charge
- Amount in minor units
- Allocation type
- Allocated by staff or system
- Idempotency key
- Allocation timestamp
- Reversal relationship
- Audit event

Do not mutate allocations silently. Corrections must create reversal or compensating records.

## Idempotency

Duplicate callbacks must credit exactly once, including concurrent duplicates. Use a database-level uniqueness boundary such as `(provider_profile_id, environment, provider_transaction_id)` plus transactional processing.

## Reversals

Reversals must create compensating ledger and allocation records. Do not delete original payment, allocation, or ledger records.

## Transaction Status

Daraja transaction-status capability should be used as a verification tool only where sandbox evidence proves the configured product supports it. Do not assume transaction query is enabled for every product.

## Reconciliation

Support import of M-PESA statements through a mapping layer. Do not assume one permanent CSV layout.

Detect:

- Callback matched to statement
- Statement transaction missing callback
- Callback missing from statement
- Duplicate transaction
- Amount mismatch
- Account-reference mismatch
- Unmatched payer
- Reversal
- Manually resolved item

