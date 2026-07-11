# Till Workflow

## Intended Use

Till payments may be useful when a subscriber pays using Buy Goods rather than Paybill account references. Till matching is more ambiguous and must be safer by default.

The Till number is not configured in Phase 0 and must remain empty until supplied by SuperSurf.

## Matching Rules

Till payments must not be matched by amount alone.

Allowed matching signals:

- Payer phone number is an authorized payer for exactly one subscriber
- Payer phone number has a reliable recent payment history for exactly one subscriber
- Optional manually entered reference if supported by the configured payment flow
- Manual Finance or Owner resolution

Ambiguous Till payments must remain unmatched.

## Outcomes

| Condition | Result |
| --- | --- |
| Valid callback, payer phone uniquely maps to authorized payer | Credit wallet and run renewal allocation |
| Valid callback, payer phone maps to multiple subscribers | Create unmatched payment |
| Valid callback, payer phone unknown | Create unmatched payment |
| Valid callback, amount equals a plan but payer is unknown | Create unmatched payment |
| Duplicate callback | No additional credit |
| Invalid callback | Credit nothing |
| Reversal | Create compensating ledger entries |

## Operational Guidance

Receipts and payment instructions should strongly prefer Paybill with account reference if SuperSurf wants automatic matching. Till should be treated as lower-confidence and reconciliation-heavy unless SuperSurf's product setup provides a reliable reference.

