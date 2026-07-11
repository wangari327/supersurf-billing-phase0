# Phase 4 Package Assignments

Phase 4 adds manual package assignment and immutable subscription history only. It lets an authorized operator attach an active package snapshot to an active service, change the package immediately, or end the current subscription immediately.

Phase 4 does not create charges, invoices, discounts, wallets, ledger entries, payments, M-PESA workflows, renewals, expiry enforcement, grace-state automation, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, installation fees, equipment billing, customer portals, notifications, or live network actions.

## Data Model

`billing.Subscription` stores:

- UUID primary key
- protected service foreign key
- protected plan foreign key
- status limited to `active` or `ended`
- aware `starts_at`
- nullable `ended_at`
- immutable package snapshot fields copied from the source package:
  - package name
  - download speed
  - integer KES minor-unit price
  - currency
  - duration days
  - grace period hours
- creation and update timestamps

Snapshots do not change when an operator later edits or deactivates the source package.

## Constraints

The database enforces:

- at most one active subscription per service
- active subscriptions have no end time
- ended subscriptions have an end time
- positive price, download speed, and duration
- non-negative grace period
- fixed `KES` currency

The model also rejects naive datetimes.

## Lifecycle

Assignment rules:

- package must be active
- service must be active
- subscriber must be active
- service must not already have an active subscription
- `starts_at` is generated from `timezone.now()`

Package changes:

- end the current active subscription
- create a new active subscription
- use the same timestamp for the old `ended_at` and new `starts_at`
- reject changing to the same package
- reject changing an already ended subscription

Ending:

- sets `ended_at` from `timezone.now()`
- does not deactivate the service
- does not deactivate the subscriber
- does not create a replacement subscription
- does not reactivate ended rows

## Immutability

After creation, application code rejects changes to:

- service
- plan
- start time
- all package snapshot fields

Model save, queryset update, queryset delete, and bulk update/delete paths are blocked for protected fields or deletion. These are application-level protections and do not protect against direct database access by a database administrator or compromised database credentials.

## Permissions

Subscription information on subscriber pages requires both:

- `subscribers.view_service`
- `billing.view_subscription`

Mutation routes require:

- `subscribers.view_service`
- `billing.add_subscription` for first assignment
- `billing.change_subscription` for package changes and ending

Owner receives all installed permissions. Administrator receives view/add/change subscription permissions. Finance, NOC, SuperSurf Support, and Read Only receive view subscription permission only. Ordinary roles do not receive `billing.delete_subscription`.

## Audit

Required audit actions:

- `subscription.assigned`
- `subscription.package_changed`
- `subscription.ended`

Audit metadata is limited to service reference, subscription UUID, plan UUID, snapshotted package name, integer price, speed, status transition, effective timestamp, and changed field names. It must not contain raw POST payloads, CSRF tokens, phone numbers, email addresses, subscriber names, payment data, or credentials.

## Admin

`Subscription` is registered read-only in Django admin. Admin add, change, delete, and bulk delete are disabled. The audited operator workflow is the supported mutation path.
