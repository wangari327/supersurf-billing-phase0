# Paybill Workflow

## Intended Use

Paybill is the preferred payment path for account-reference-based subscriber matching when SuperSurf has a Paybill product configured.

The Paybill shortcode is not configured in Phase 0 and must remain empty until supplied by SuperSurf.

## Matching Rules

Use the Paybill account reference as the primary matching signal.

Normalize account references for matching:

- Trim leading and trailing whitespace
- Compare case-insensitively
- Ignore common separators such as spaces, hyphens, and slashes where safe
- Preserve the original reference for audit and reconciliation

Do not match by amount alone.

## Outcomes

| Condition | Result |
| --- | --- |
| Valid callback, account reference matches active subscriber service | Credit wallet and run renewal allocation |
| Valid callback, account reference matches suspended subscriber service | Credit wallet and run renewal/reactivation allocation |
| Valid callback, account reference ambiguous | Create unmatched payment requiring manual resolution |
| Valid callback, account reference missing | Create unmatched payment |
| Duplicate callback | No additional credit |
| Invalid callback | Persist rejected event if safe; credit nothing |
| Reversal | Create compensating ledger entries |

## Manual Resolution

Manual matching must:

- Require Finance or Owner permission
- Show payer, amount, date, transaction ID, and original account reference
- Create audit history
- Preserve original unmatched-payment record
- Credit through the same ledger allocation service used by callbacks

