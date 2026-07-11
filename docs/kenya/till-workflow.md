# Till Workflow

## Intended Use

Till payments may be useful when a subscriber pays using Buy Goods rather than Paybill account references. Till matching is more ambiguous and must be safer by default.

The Till number is not configured in Phase 0.5 and must remain empty until supplied by SuperSurf.

## Provider Profile

Till must be configured as its own provider profile:

- Product type: Till
- Environment: sandbox or production
- Till identifier
- Enabled state
- Credential reference
- Callback configuration
- Reconciliation configuration

A sandbox Till transaction must not collide with a production Till transaction. Provider transaction uniqueness must include provider profile and environment.

## Matching Rules

Till payments must not be matched by amount alone.

Do not assume Till callbacks always provide payer MSISDN or account reference. The exact fields must be verified in sandbox evidence before implementation.

Allowed matching signals after evidence confirms the fields:

- Payer phone number is an authorized payer for exactly one subscriber
- Payer phone number has a reliable recent payment history for exactly one subscriber
- Optional reference if supported by the configured product flow
- Manual Finance or Owner resolution

Ambiguous Till payments must remain unmatched through an `UnmatchedPaymentCase` linked to the canonical `Payment`.

## Outcomes

| Condition | Result |
| --- | --- |
| Valid callback, payer phone uniquely maps to authorized payer | Create canonical `Payment`, create `PaymentAllocation`, and run later renewal allocation |
| Valid callback, payer phone maps to multiple subscribers | Create canonical `Payment` and open `UnmatchedPaymentCase` |
| Valid callback, payer phone unknown | Create canonical `Payment` and open `UnmatchedPaymentCase` |
| Valid callback, amount equals a plan but payer is unknown | Create canonical `Payment` and open `UnmatchedPaymentCase` |
| Duplicate callback | Locate existing `Payment`; no additional allocation |
| Invalid callback with no valid financial transaction | Credit nothing; do not create a financial `Payment` |
| Reversal | Create compensating allocation and ledger records |

## Operational Guidance

Receipts and payment instructions should strongly prefer Paybill with account reference if SuperSurf wants automatic matching. Till should be treated as lower-confidence and reconciliation-heavy unless SuperSurf's product setup provides a reliable reference.

