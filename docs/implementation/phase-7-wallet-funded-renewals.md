# Phase 7 Wallet-Funded Renewals

Phase 7 adds operator-triggered Wallet-funded activation and renewal charges. It connects three existing concepts in one atomic workflow:

- `BillingPeriod` records service time.
- `LedgerEntry` debits an existing subscriber Wallet.
- `BillingCharge` links the billing period and ledger debit.

This phase does not create payments, M-PESA, Paybill, Till, payment callbacks, cash or bank payment recording, invoices, receipts, discounts, bundles, customer-specific prices, automatic wallet allocation, automatic renewal, automatic suspension, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, notifications, customer portals, installation fees, equipment billing, or live network actions.

Manual Wallet credits remain accounting adjustments only. They are not proof that money was received.

## Data Model

`billing.BillingCharge` stores:

- UUID primary key
- protected service foreign key
- protected subscription snapshot foreign key
- protected billing-period one-to-one link
- protected wallet foreign key
- protected ledger-entry one-to-one link
- unique operation ID
- charge type: `activation` or `renewal`
- positive integer KES minor-unit amount
- fixed `KES` currency
- required trimmed operator reason, limited to 240 characters
- protected creating operator foreign key
- creation timestamp

`BillingCharge` records are append-only in application code. Model save, queryset update, bulk update, model delete, and queryset delete paths reject changes after creation, including creation timestamp changes. Direct privileged database writes remain outside application-level controls.

The ledger has a new `billing_charge` entry type. Billing-charge ledger entries are always debits, cannot be reversed through the manual reversal workflow, and are linked to exactly one `BillingCharge`.

## Charge Rules

Wallet-funded activation is allowed only when:

- the subscriber is active
- the service is active
- the service has an active subscription
- the service has no existing billing period
- the subscriber already has a Wallet
- the Wallet balance is at least the active subscription snapshot price

Wallet-funded renewal is allowed only when:

- the subscriber is active
- the service is active
- the service has an active subscription
- the submitted expected previous period is the latest billing period
- the subscriber already has a Wallet
- the Wallet balance is at least the active subscription snapshot price

The charge amount is exactly the current active `Subscription` snapshot price. Edits to the package catalog after assignment do not change existing subscription snapshot prices. Partial Wallet balances are rejected and do not create partial time. Overpayment remains as Wallet credit after the charge.

## Date Rules

Phase 7 reuses the reviewed Phase 5 billing-period date rules:

- first activation starts at the effective timestamp
- early renewal starts at the previous period expiry
- renewal during grace also starts at the previous period expiry
- late renewal starts at the renewal effective timestamp
- zero-hour grace uses expiry as the grace boundary

## Atomicity And Idempotency

Wallet-funded posting runs in a single database transaction. It locks in this order:

1. service and subscriber
2. existing Wallet
3. current active Subscription
4. latest BillingPeriod
5. latest LedgerEntry

The operation creates the billing period, billing-charge ledger debit, billing charge, and audit events together. If any step fails, none of those records remain.

Operation IDs make equivalent retries idempotent. A retry with the same operation ID, service, charge type, expected previous period, amount, and reason returns the existing `BillingCharge`. Reusing an operation ID for a different billing charge, billing period, or ledger entry is rejected.

PostgreSQL CI is authoritative for duplicate operation, stale renewal, competing Wallet spend, and row-lock behavior. SQLite local tests skip only the PostgreSQL row-lock concurrency cases.

## Permissions

Wallet-funded activation and renewal require all of:

- `subscribers.view_subscriber`
- `subscribers.view_service`
- `billing.view_subscription`
- `billing.view_billingperiod`
- `billing.add_billingperiod`
- `billing.view_wallet`
- `billing.view_ledgerentry`
- `billing.add_ledgerentry`
- `billing.view_billingcharge`
- `billing.add_billingcharge`

Administrator and Finance receive `view_billingcharge` and `add_billingcharge`. SuperSurf Support and Read Only receive `view_billingcharge` only. NOC receives no Wallet, LedgerEntry, or BillingCharge permissions in this phase.

Ordinary roles do not receive `billing.change_billingcharge` or `billing.delete_billingcharge`.

## Operator UI

Subscriber detail shows Wallet-funded activation or renewal controls only when the operator can view the service, subscription, billing period, Wallet, ledger, and BillingCharge data and can add the required period, ledger entry, and charge records.

The UI displays:

- Wallet balance
- active package price
- amount required
- remaining balance after charge when sufficient
- missing Wallet or insufficient balance messages

Manual activation and renewal controls remain available to authorized billing-period operators, but they are labeled as manual uncharged actions. Manual uncharged periods do not deduct Wallet credit and do not confirm payment.

Billing-period history marks periods as `Wallet funded` when a linked charge exists and `Manual uncharged` otherwise. Wallet detail shows the service reference for billing-charge debits when the operator also has service visibility. Operation IDs are not displayed in ordinary templates.

## Audit

Successful Wallet-funded postings record:

- `billing_period.activated` or `billing_period.renewed`
- `billing_charge.posted`
- `wallet.billing_charge`

Audit metadata is limited to generated identifiers, sequence numbers, charge type, integer amount, balance after entry, currency, relevant timestamps, and service or subscriber references. It does not store operation IDs, raw POST payloads, phone numbers, email addresses, subscriber display names, payment claims, M-PESA information, credentials, or CSRF tokens.

## Admin

`BillingCharge` is registered read-only in Django admin. Admin add, change, delete, and bulk delete are disabled. The audited operator UI and service layer are the only supported application mutation paths.
