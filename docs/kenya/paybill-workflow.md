# Paybill Workflow

## Intended Use

Paybill is the preferred payment path for account-reference-based subscriber matching when SuperSurf has a Paybill product configured.

The Paybill shortcode is not configured in Phase 0.5 and must remain empty until supplied by SuperSurf.

## Provider Profile

Paybill must be configured as its own provider profile:

- Product type: Paybill
- Environment: sandbox or production
- Shortcode
- Enabled state
- Credential reference
- Callback configuration
- Reconciliation configuration

A sandbox Paybill transaction must not collide with a production Paybill transaction. Provider transaction uniqueness must include provider profile and environment.

## Matching Rules

Use the Paybill account reference as the primary matching signal only after sandbox evidence confirms the exact field and behavior.

Normalize account references for matching:

- Trim leading and trailing whitespace
- Compare case-insensitively
- Ignore common separators such as spaces, hyphens, and slashes where safe
- Preserve the original reference for audit and reconciliation

Do not match by amount alone.

## Outcomes

| Condition | Result |
| --- | --- |
| Valid callback, account reference matches active subscriber service | Create canonical `Payment`, create `PaymentAllocation`, and run later renewal allocation |
| Valid callback, account reference matches suspended subscriber service | Create canonical `Payment`, allocate safely, and run later renewal/reactivation allocation |
| Valid callback, account reference ambiguous | Create canonical `Payment` and open `UnmatchedPaymentCase` |
| Valid callback, account reference missing | Create canonical `Payment` and open `UnmatchedPaymentCase` |
| Duplicate callback | Locate existing `Payment`; no additional allocation |
| Invalid callback with no valid financial transaction | Record rejected webhook where safe; do not create a financial `Payment` |
| Reversal | Create compensating allocation and ledger records |

## Manual Resolution

Manual matching must:

- Require Finance or Owner permission
- Show payer, amount, date, transaction ID, original account reference, and provider profile
- Create audit history
- Preserve original `Payment` and `UnmatchedPaymentCase`
- Credit through the same allocation service used by callbacks
- Use an allocation idempotency key

