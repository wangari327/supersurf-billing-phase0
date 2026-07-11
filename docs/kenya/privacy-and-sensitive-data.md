# Privacy And Sensitive Data

## Collection Principle

Collect only what SuperSurf needs to operate the service. Do not collect identity information merely because a field exists.

## Sensitive Fields

Sensitive fields include:

- National ID number
- Passport number
- KRA PIN
- Company registration number
- M-PESA payer details where linked to a person
- Subscriber notes containing identity or access details
- Router credentials
- RADIUS shared secrets
- Integration credentials

## Handling Requirements

Sensitive identity information must:

- Be optional
- Be access-controlled
- Be masked in ordinary views
- Never appear in logs
- Never appear in URLs
- Not be visible to support staff without permission
- Be encrypted where appropriate
- Be excluded from ordinary exports unless explicitly authorized

## Role Visibility

SuperSurf Support should see service status, renewal instructions, limited payment state, tickets, and notes. Support should not see full identity numbers, M-PESA credentials, router credentials, RADIUS shared secrets, or ledger adjustment controls.

Finance may see payment and reconciliation data but not router credentials or unnecessary network secrets.

NOC may see service and session data but not unnecessary financial adjustment controls or M-PESA credentials.

