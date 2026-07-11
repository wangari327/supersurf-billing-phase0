# Kenya Privacy Operations

This document is an operational planning document for later review. It does not claim legal certification or statutory compliance.

## Field Purpose Register

Before production, SuperSurf should maintain a register describing the purpose for each collected field:

- Subscriber name or business name
- Phone numbers
- Authorized payer numbers
- Service location fields
- GPS coordinates
- Installation notes
- Support notes
- Optional identity fields
- Payment records
- Audit events

Fields without a clear operational purpose should not be collected.

## Retention Schedule

Define retention periods for:

- Active subscriber records
- Terminated subscriber records
- Payment and receipt records
- Support tickets
- Audit events
- Uploaded M-PESA statements
- Backups
- Security logs

Financial and operational retention may differ. Retention decisions require owner and legal review before production.

## Terminated Subscribers

Terminated-subscriber records should be retained only as long as needed for legitimate operational, financial, support, audit, or legal purposes. Ordinary operator views should clearly show terminated status and should not expose sensitive identity fields unless permitted.

## Correction Workflow

SuperSurf should provide a staff workflow to correct inaccurate subscriber data:

- Record who requested the correction.
- Record who approved and performed it.
- Preserve audit history where safe.
- Avoid overwriting financial or audit facts.

## Subscriber Data Access And Export

Future export workflows should:

- Require Owner or explicitly delegated permission.
- Record an audit event.
- Exclude secrets and unrelated staff data.
- Mask or omit sensitive identity fields unless explicitly authorized.
- Prevent CSV formula injection.

## Anonymization Or Deletion

Where deletion or anonymization is applicable:

- Confirm the subscriber identity through an approved process.
- Preserve records that must remain for financial, audit, security, or legal reasons.
- Prefer anonymization for operational notes when full deletion would damage auditability.
- Record the action in the audit trail.

## Breach Response

Maintain a breach-response process covering:

- Triage and containment
- Credential rotation
- Backup and log preservation
- Subscriber impact review
- Regulatory or legal review
- Owner approval for communications
- Post-incident corrective actions

## Staff Access Reviews

Review staff access periodically:

- Confirm active staff accounts.
- Confirm role assignments.
- Remove access for departed staff.
- Review privileged actions.
- Review failed-login and lockout patterns.

## Backup Retention

Backup retention must align with the data retention schedule. Off-site backup locations and access controls require review before production.

## Audit-Event Retention

Audit events should be retained long enough to support security investigations, financial review, and operational accountability. The application must not provide ordinary update or delete paths for audit events.

## Third-Party Processor Inventory

Maintain an inventory of third parties that may process SuperSurf data, including:

- Hosting provider
- Backup storage provider
- Email provider
- SMS or WhatsApp provider if later configured
- Payment provider
- Monitoring provider if later configured

Record the purpose, data categories, location, and access controls for each.

## Off-Site Storage Location Review

Before production, review where off-site backups and exported files are stored, who can access them, and how encryption keys are recovered.

