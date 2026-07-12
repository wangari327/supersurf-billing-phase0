# SuperSurf Architecture Overview

## Architecture Style

Use a modular Django monolith.

Do not create a microservice system for the MVP. Do not create one Django app per noun. Start with bounded modules:

- `core`
- `users`
- `subscribers`
- `billing`
- `payments`
- `network`
- `support`
- `audit`

The database should be PostgreSQL. Background jobs should use Celery with Redis or a reviewed broker alternative. The UI should use Django templates, HTMX, Tailwind CSS, and minimal JavaScript only where needed.

## Implemented Through Phase 8

The current application implements the Django foundation, staff users and roles, audit events, organization defaults, package catalog, subscriber registry, service references, manual package assignment with immutable subscription history, manual billing periods with derived billing state, account-level wallet ledger accounting, operator-triggered Wallet-funded activation and renewal charges, and canonical payment records with fake-provider Wallet credits.

Phase 8 fake payment ingestion creates provider-neutral payments, matches exact `SS000001`-style account references, credits the account-level Wallet through `payment_credit` ledger entries, and opens unmatched-payment cases when a safe account match is unavailable. Matched payments do not automatically renew services, spend Wallet credit, create invoices or receipts, run reconciliation imports, call Safaricom or Daraja, process real M-PESA callbacks, configure Paybill or Till credentials, provision network access, or perform live network actions.

## Primary Components

| Component | Responsibility |
| --- | --- |
| Django web app | Operator UI, webhook endpoints, APIs, admin, RBAC |
| PostgreSQL | Source of truth for subscribers, ledger, payments, audit, RADIUS integration tables |
| Celery workers | Payment allocation, provisioning jobs, retries, reports, backups |
| Scheduler | Expiry jobs, grace transitions, suspension jobs, reconciliation reminders, backup jobs |
| Redis or reviewed broker | Task broker and cache where appropriate |
| FreeRADIUS | PPPoE authentication and accounting using PostgreSQL SQL integration |
| MikroTik RouterOS | PPPoE termination, sessions, network enforcement, disconnect actions |
| Caddy | Reverse proxy, TLS, security headers |
| Backup tooling | PostgreSQL dumps, uploaded statements, branding assets, encrypted off-site copy |

## Key Design Principles

- Financial state lives in PostgreSQL before network actions.
- Payment processing is idempotent.
- Ledger entries are append-only.
- Network actions are asynchronous, audited, retryable, and dry-run by default.
- RouterOS and FreeRADIUS downtime must not lose financial transactions.
- Integration packages must be wrapped behind internal interfaces.
- SuperSurf-specific logic belongs in explicit services, not scattered template code or model signals.

## Proposed Module Responsibilities

### core

Organization settings, Kenya defaults, branding, secure settings registry, health/readiness endpoints, common utilities.

### users

Staff users, roles, permissions, TOTP, login throttling, sessions, staff audit events.

### subscribers

Subscribers, service references, account numbers, and active/inactive status. Service locations, payer numbers, and notes remain future work.

### billing

Packages, manual subscription history, manual billing-period history, manual renewals, derived billing state, account-level wallets, append-only ledger entries, manual adjustments, reversals, operator-triggered Wallet-funded activation and renewal charges, canonical payments, fake payment ingestion, Wallet payment credits, and unmatched-payment cases. Invoices, receipts, real provider adapters, reconciliation imports, expiry enforcement, automatic renewal, automatic suspension, and grace-state automation remain future work.

### payments

Future thin provider adapters for M-PESA callbacks, Paybill matching, Till matching, reversals, statement imports, and reconciliation. Phase 8 canonical payments currently live in the `billing` app and expose only fake-provider ingestion for development and tests.

### network

NAS/router inventory, RADIUS provisioning, RADIUS accounting views, sessions, RouterOS adapter, CoA/disconnect jobs, dry-run safety.

### support

SuperSurf Support tickets, subscriber notes, categories, priorities, statuses, assignments.

### audit

Append-only audit trail, redaction, export events, before/after snapshots where safe.

## Phase 1 Foundation Scope

Phase 1 should create the Django foundation, Docker Compose, PostgreSQL, broker, staff authentication, RBAC, organization seed, configurable branding, base UI, audit framework, CI, and initial tests.

This historical Phase 1 scope remains closed. Later phases must still explicitly approve real provider payments, RADIUS, MikroTik, and production M-PESA behavior before implementation.
