# Phase 3 Subscriber Registry

Phase 3 adds only subscriber account records and service references. It gives SuperSurf stable identifiers for later reviewed phases without introducing billing, subscription, payment, PPPoE, RADIUS, RouterOS, installation, equipment, or network-provisioning behavior.

## Scope

Included:

- `subscribers` Django app
- `Subscriber` model
- `Service` model
- one internal `SubscriberSequence` allocation model
- subscriber list, detail, create, edit, deactivate, and reactivate workflows
- service create, edit, deactivate, and reactivate workflows
- audited subscriber and service mutations
- dashboard and navigation links gated by `subscribers.view_subscriber`
- role permissions for viewing and mutation

Excluded:

- subscriptions
- package assignment
- discounts
- invoices
- payments
- wallets
- ledgers
- M-PESA
- renewals
- expiry and suspension automation
- FreeRADIUS
- PPPoE credentials
- RouterOS
- network provisioning
- installation and equipment billing
- customer portals
- support tickets
- live network actions

## Identifiers

Subscriber accounts use backend-generated account numbers such as `SS000001`. The number is unique, immutable in application code, and never reused by the allocator.

Services use backend-generated references such as `SS000001-01`. The suffix is allocated from `01` through `99` per subscriber. Attempting to allocate a 100th service raises a validation error.

Allocation uses `transaction.atomic()` with `select_for_update()` row locking on the internal sequence rows. The account sequence is seeded idempotently by migration. Service sequences are created per subscriber on first service allocation. If an unexpected identifier collision is found, allocation advances forward.

A future PPPoE username convention may lowercase the service reference, for example `ss000001-01`. Phase 3 does not add PPPoE fields, credentials, RADIUS rows, router references, or network provisioning actions.

## Data Model

`Subscriber` stores:

- UUID primary key
- immutable `account_number`
- customer type, limited to individual or business
- display name
- normalized primary Kenya phone number
- optional email
- active flag
- creation and update timestamps

`Service` stores:

- UUID primary key
- protected subscriber foreign key
- immutable service number
- immutable service reference
- optional label, trimmed and limited to 120 characters
- active flag
- creation and update timestamps

Phase 3 intentionally does not store identity numbers, KRA PINs, company registration numbers, date of birth, gender, installation location, sensitive notes, package links, prices, discount fields, invoice fields, payment fields, wallet fields, payer fields, IP addresses, MAC addresses, router references, tower references, RADIUS fields, PPPoE fields, installation fees, or equipment fields.

## Phone Normalization

The subscriber primary phone is required, not unique, and normalized for Kenya only:

| Input | Stored value |
| --- | --- |
| `0712345678` | `+254712345678` |
| `0112345678` | `+254112345678` |
| `254712345678` | `+254712345678` |
| `+254712345678` | `+254712345678` |

Spaces, hyphens, and parentheses are removed before validation.

## Mutability

Identifiers are omitted from forms and marked immutable in application code:

- `Subscriber.account_number`
- `Service.subscriber`
- `Service.service_number`
- `Service.service_reference`

Model `save()`, queryset `update()`, and `bulk_update()` reject changes to those fields. These are application-level controls. Direct database access by a database administrator or an attacker with database credentials can still alter rows.

There are no delete routes. Normal workflows deactivate and reactivate subscribers or services. The `Service.subscriber` foreign key uses `PROTECT`, so a subscriber with services is protected from ordinary ORM deletion.

## Permissions

- Owner receives all installed Django permissions.
- Administrator receives view, add, and change permissions for subscribers and services.
- Finance, NOC, SuperSurf Support, and Read Only receive view permissions for subscribers and services.
- Ordinary roles do not receive delete permissions.

Subscriber profile data requires `subscribers.view_subscriber`. Service data is a separate visibility surface and requires `subscribers.view_service`. A user with subscriber view but not service view can open subscriber list and detail pages, but must not see service references, labels, statuses, service lists, service counts, service-reference search results, or dashboard service counts.

## Audit

Audit actions:

- `subscriber.created`
- `subscriber.updated`
- `subscriber.deactivated`
- `subscriber.reactivated`
- `service.created`
- `service.updated`
- `service.deactivated`
- `service.reactivated`

Targets are the subscriber account number or service reference. Metadata is limited to generated identifiers, changed field names, service numbers, and status transitions. Raw POST payloads, full phone numbers, emails, display names, package data, billing data, payment data, PPPoE credentials, RADIUS data, router data, and installation details are not stored in audit metadata.

## Admin

`Subscriber` and `Service` are registered read-only in Django admin. The internal allocation sequence is not registered in admin and has no default Django permissions.

## Migrations

- `subscribers.0001_initial` creates the subscriber, service, and internal sequence tables.
- `subscribers.0002_seed_account_sequence` idempotently creates the global account sequence row.

No fake subscribers, names, phone numbers, or services are seeded.
