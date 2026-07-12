# Phase 5 Billing Periods

Phase 5 adds append-only manual billing periods and manual renewals. A billing period records the access window an operator chose to activate or renew for a service. It does not claim that money was received.

Phase 5 does not create charges, invoices, discounts, wallets, ledger entries, payments, M-PESA workflows, automatic renewals, automatic expiry jobs, automatic suspension, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, installation fees, equipment billing, customer portals, notifications, or live network actions.

## Data Model

`billing.BillingPeriod` stores:

- UUID primary key
- protected service foreign key
- protected subscription foreign key
- per-service sequence number
- period type: `activation` or `renewal`
- unique internal operation ID
- nullable protected previous-period foreign key
- aware effective, start, expiry, and grace-until timestamps
- immutable commercial snapshot fields copied from the active subscription:
  - package name
  - download speed
  - integer KES minor-unit price
  - currency
  - duration days
  - grace period hours
- creation timestamp

There is no `updated_at` field because billing period rows are append-only.

## Constraints

The database enforces:

- unique service and sequence number
- globally unique operation ID
- positive sequence, price, download speed, and duration
- non-negative grace period
- fixed `KES` currency
- valid period type
- expiry after start
- grace until at or after expiry
- activation periods with no previous period
- renewal periods with a previous period
- one direct successor for each previous period

The model and service layer also validate that a previous period belongs to the same service.

## Date Rules

Period dates always come from the active subscription snapshot. Operators do not enter effective, start, expiry, or grace dates.

For the default SuperSurf packages, periods are 30 days and the default grace period is 24 hours. Those values are configurable through the assigned package and copied into the active subscription snapshot. Later package edits do not change existing subscriptions or billing periods.

Rules:

- First activation starts at the effective timestamp.
- Early renewal starts at the latest period's expiry, preserving remaining days.
- Renewal during grace also starts at the original expiry and extends from that expiry.
- Late renewal starts at the manual renewal timestamp.
- A zero-hour grace period means `grace_until` equals `expires_at`.
- Each service has an independent period sequence and expiry timeline.

## Derived State

Billing state is derived at read time and is not persisted:

- `unactivated`: no billing periods
- `active`: current time is before the latest expiry
- `grace`: current time is at or after expiry and before grace-until
- `expired`: current time is at or after grace-until

State calculation does not mutate the service, subscriber, or subscription. It does not suspend network access or create a background job.

## Locking And Idempotency

Period creation uses `transaction.atomic()` and the service-first locking order:

1. lock the service and subscriber
2. lock the active subscription
3. lock the latest billing period
4. allocate the next sequence and create the new period

The service row lock protects sequence allocation, and database uniqueness remains the final concurrency guard.

Manual action forms include a hidden operation ID and the expected previous period ID. Duplicate submission of the same equivalent operation returns the original period without a second audit event. Reusing an operation ID for a conflicting operation is rejected. Stale renewal forms are rejected after locks are acquired if the latest period changed.

PostgreSQL CI is authoritative for row-lock and concurrency behavior. SQLite local tests skip only the true row-lock concurrency cases.

## Permissions

Viewing billing periods requires all of:

- `subscribers.view_service`
- `billing.view_subscription`
- `billing.view_billingperiod`

Creating a manual activation or renewal requires all of:

- `subscribers.view_service`
- `billing.view_subscription`
- `billing.add_billingperiod`

Owner receives all installed permissions. Administrator and Finance receive `billing.view_billingperiod` and `billing.add_billingperiod`. NOC, SuperSurf Support, and Read Only receive `billing.view_billingperiod` only. Ordinary roles do not receive `billing.change_billingperiod` or `billing.delete_billingperiod`.

## Audit

Successful new periods record:

- `billing_period.activated`
- `billing_period.renewed`

Audit metadata is limited to service reference, subscription UUID, billing-period UUID, sequence number, period type, previous-period UUID, package name, speed, integer price, duration, grace duration, period dates, and derived state after creation.

Audit metadata must not contain raw POST payloads, operation IDs, phone numbers, email addresses, subscriber display names, payment claims, wallet information, credentials, or CSRF tokens.

## Admin

`BillingPeriod` is registered read-only in Django admin. Admin add, change, delete, and bulk delete are disabled. The audited operator workflow is the supported application mutation path.

These are application-level controls. Privileged direct database access or compromised database credentials can still alter rows outside the application boundary.
