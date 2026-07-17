# Integration Boundaries

External dependencies must be wrapped behind internal interfaces.

Phase 9.1 is an inbound-only exception with no external client: the HTTP callback view captures immutable evidence, then a dedicated internal sandbox Paybill service reads that event and calls the private provider-neutral canonical payment core. It does not implement `MpesaProvider`, authenticate to Daraja, or make an outbound network request. The broader interfaces below remain future boundaries.

## Required Interfaces

| Interface | Purpose |
| --- | --- |
| `MpesaProvider` | Shared Daraja auth, request signing or headers, transaction status, callback validation |
| `PaybillProvider` | Paybill-specific C2B behavior and matching payloads |
| `TillProvider` | Till-specific C2B behavior and lower-confidence matching |
| `RouterOSAdapter` | Router health, sessions, safe disconnects, reviewed write commands |
| `RadiusProvisioningService` | RADIUS user/profile provisioning through PostgreSQL-backed state |
| `RadiusCoaClient` | CoA and Disconnect-Request where lab-verified |
| `PhoneNumberNormalizer` | Kenyan phone parsing and E.164 formatting |
| `MoneyFormatter` | KES display and export formatting |
| `CsvStatementParser` | M-PESA statement imports through mapping profiles |
| `NotificationProvider` | Future SMS, email, or WhatsApp notifications |
| `StorageProvider` | Uploaded statements, receipt assets, branding assets, backup output |

## Thin Integration Policy

Where no trustworthy maintained package exists, build only a thin integration using official documentation:

- Use mature HTTP clients.
- Use maintained retry libraries.
- Use standard cryptographic libraries.
- Store payload fixtures.
- Write comprehensive tests.
- Document rejected wrappers.

Do not write custom HTTP stacks, OAuth frameworks, cryptographic algorithms, webhook frameworks, database drivers, or task queues.
