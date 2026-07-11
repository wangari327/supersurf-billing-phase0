# Phase 2 Package Catalog

Phase 2 adds only the operator-managed package catalog. Operators see the term "Package"; the internal Django model remains `billing.Plan` to match the approved architecture.

## Scope

Included:

- `billing` Django app
- `Plan` model
- package list, detail, create, edit, deactivate, and reactivate workflows
- initial SuperSurf packages
- package audit events
- package permissions

Excluded:

- subscribers
- services
- subscriptions
- discounts
- promotional pricing
- payments
- wallets
- ledgers
- invoices
- M-PESA
- FreeRADIUS
- PPPoE
- RouterOS
- network provisioning
- renewal automation
- installation fees
- equipment billing
- customer portals

## Package Fields

`Plan` stores:

- UUID primary key
- name
- download speed in Mbps
- price in integer KES minor units
- fixed currency `KES`
- duration in days
- grace period in hours
- optional description
- active flag
- creation and update timestamps

No upload speed, RADIUS profile, router field, subscriber field, renewal date, discount field, promotional price, installation charge, or equipment charge is stored on packages.

## Initial Packages

The idempotent seed migration creates missing packages only:

| Package | Download | Price | Minor units | Duration | Grace | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 5 Mbps | 5 Mbps | KSh 500 | 50000 | 30 days | 24 hours | Active |
| 15 Mbps | 15 Mbps | KSh 1,500 | 150000 | 30 days | 24 hours | Active |
| 30 Mbps | 30 Mbps | KSh 2,000 | 200000 | 30 days | 24 hours | Active |

The reverse migration is a no-op so rolling migrations backward does not unexpectedly delete business data.

## Money

Operators enter ordinary KSh values such as `500`, `1500`, `2000`, or `1500.50`. Forms convert KSh to integer minor units using `Decimal`, never binary floating point. UI displays prices with KSh and thousands separators.

## Deactivation

Normal workflows never permanently delete packages. Operators deactivate packages and may reactivate them later. There is no package delete route.

## Permissions

- `billing.view_plan`: package list and detail
- `billing.add_plan`: package creation
- `billing.change_plan`: package edit, deactivate, and reactivate

Owner receives permissions through the existing all-permissions behavior. Administrator can view, add, and change packages. Finance, NOC, SuperSurf Support, and Read Only can view packages only. Ordinary roles do not receive `billing.delete_plan`.

## Audit

Audit actions:

- `package.created`
- `package.updated`
- `package.deactivated`
- `package.reactivated`

Audit metadata is bounded to changed field names plus safe old and new package values. Raw POST payloads are not stored. The operator reason is required and stored as the audit event reason, not on the `Plan` model.

## Future Work

Discounts remain future work and are not hard-coded into packages. Later phases must explicitly review subscriber subscriptions, payments, wallets, ledgers, invoices, M-PESA, RADIUS, RouterOS, and network behavior before implementation.
