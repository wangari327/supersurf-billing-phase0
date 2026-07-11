# M-PESA Payment Workflows

## Scope

Initial M-PESA support should focus on safely recording and allocating incoming Paybill and Till payments. Customer-facing STK Push is not required for the internal MVP.

Do not use production credentials in development.

Do not implement a mobile-money aggregator. SuperSurf Billing should integrate only with SuperSurf's configured Daraja products.

## Shared Workflow

1. Receive callback over HTTPS.
2. Validate source and request shape according to current Daraja documentation and SuperSurf settings.
3. Persist raw callback payload with redacted logs.
4. Create or locate an immutable payment event by provider transaction ID.
5. Enforce idempotency before crediting.
6. Normalize amount into integer minor units.
7. Normalize payer phone if present.
8. Match payment according to Paybill or Till rules.
9. Credit subscriber wallet or create unmatched payment.
10. Apply renewal logic only through the ledger and subscription engine.
11. Create audit event.
12. Expose reconciliation status.

## Idempotency

Duplicate callbacks must credit exactly once, including concurrent duplicates. Use database-level uniqueness on provider transaction IDs plus transactional processing.

## Reversals

Reversals must create compensating ledger entries. Do not delete original payment or ledger records.

## Transaction Status

Daraja transaction-status capability should be used as a verification tool where supported by the configured product. Phase 1 must not assume all product combinations expose identical status or reconciliation behavior.

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

