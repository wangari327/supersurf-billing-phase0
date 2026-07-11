# ADR 0004: Wrap External Integrations

## Status

Proposed for Phase 1.

## Context

Daraja wrappers, RouterOS API clients, RADIUS clients, phone libraries, and CSV packages may change or prove unsuitable. SuperSurf business logic should not be coupled directly to third-party package APIs.

## Decision

Wrap external integrations behind internal interfaces:

- `MpesaProvider`
- `PaybillProvider`
- `TillProvider`
- `RouterOSAdapter`
- `RadiusProvisioningService`
- `RadiusCoaClient`
- `PhoneNumberNormalizer`
- `MoneyFormatter`
- `CsvStatementParser`

## Consequences

Positive:

- Easier package replacement.
- Cleaner tests using fakes and dry-run adapters.
- Better boundary for secrets, retries, and audit logging.

Tradeoffs:

- Slightly more code than direct package calls.
- Interfaces must stay thin to avoid unnecessary abstraction.

