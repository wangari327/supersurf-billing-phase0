# SuperSurf Brand And Product Contract

## Default Organization

The first migration and first application startup in Phase 1 must create one default organization:

| Field | Default |
| --- | --- |
| Trading name | SuperSurf |
| Billing product name | SuperSurf Billing |
| Network operations label | SuperSurf Networks |
| Customer support label | SuperSurf Support |
| Customer portal label | SuperSurf Portal |

These defaults must be editable through organization settings.

## Derived Labels

Derived labels should use the configured primary brand unless the owner edits a specific label.

Default derived labels:

- SuperSurf Billing
- SuperSurf Networks
- SuperSurf Support
- SuperSurf Portal
- SuperSurf Payments
- SuperSurf NOC
- SuperSurf Reports
- SuperSurf Radius
- SuperSurf Connect

Labels must not be permanently hardcoded in templates, emails, receipts, invoices, reports, or generated PDFs. Store them as organization settings with safe defaults.

## Editable Brand Settings

Organization settings must support:

- Primary brand name
- Registered business name
- Trading name
- Product name
- Logo
- Favicon
- Receipt heading
- Invoice heading
- Support department name
- Network department name
- Portal name
- Primary UI colour
- Secondary UI colour
- Receipt footer
- Invoice footer
- Payment instructions
- Support contacts
- Domain
- Public portal URL
- Support email
- Billing email
- NOC email
- Support phone
- WhatsApp contact, if configured later

## Real-World Values

Do not invent:

- Public domains
- Email addresses
- M-PESA Paybill numbers
- M-PESA Till numbers
- API credentials
- KRA PINs
- Business registration numbers
- Communications Authority licence numbers
- Production network credentials

Unset values must remain empty, marked not configured, editable through secure settings, and documented as required before production activation where applicable.

## Product Scope

SuperSurf Billing is initially an owner-operated modular-monolith system for one Kenyan wireless ISP. It is not initially:

- A multi-tenant SaaS platform
- A generic international billing platform
- A marketplace
- A full accounting suite
- A telecom carrier-grade BSS
- A reseller platform
- A mobile-money aggregator
- A microservice demonstration project

The product should replace recurring third-party per-client billing charges while giving SuperSurf control and visibility over subscribers, prepaid billing, M-PESA payments, wallets, invoices, receipts, ledger entries, PPPoE, FreeRADIUS, MikroTik sessions, support, audit history, backups, and reports.

