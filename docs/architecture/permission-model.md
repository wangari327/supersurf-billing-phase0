# Permission Model

## Initial Roles

| Role | Purpose |
| --- | --- |
| Owner | Full application authority, integration configuration, security configuration, financial adjustments, network approvals |
| Administrator | Operational administration, subscriber administration, plan administration, staff administration subject to restrictions |
| Finance | Fake payment ingestion, unmatched payment resolution, approved financial adjustments, financial exports |
| NOC | Sessions, router health, RADIUS status, retry provisioning, disconnect subscriber sessions |
| SuperSurf Support | Subscriber service status, tickets, notes, limited payment state, renewal instructions |
| Read Only | Authorized viewing only |

## Separation Of Duties

Finance must not change router credentials, RADIUS secrets, or network integrations.

NOC must not create manual wallet credits, alter ledger entries, or view unnecessary M-PESA credentials.

SuperSurf Support must not ingest fake payments, resolve unmatched payments, modify ledger entries, post Wallet-funded charges, change plans without authority, configure integrations, or disconnect sessions unless explicitly granted.

Read Only must not write.

## Privileged Actions

Require Owner or explicitly delegated permission:

- Integration credential changes
- M-PESA product activation
- Real payment-provider adapter activation
- Unmatched payment policy changes
- RouterOS real-write activation
- RADIUS shared-secret changes
- Financial adjustment approval
- Backup restore
- Security setting changes
- Staff role changes
- Sensitive export authorization

## Implementation Notes

Use Django auth as the base. Phase 8 payment permissions are global staff permissions: Administrator and Finance can ingest fake payments and resolve unmatched cases; SuperSurf Support and Read Only can view payment and unmatched-case records; NOC has no payment permissions. Evaluate `django-guardian` or `rules` for object-level permissions where necessary. Do not overbuild a policy engine before a reviewed phase proves the need.
