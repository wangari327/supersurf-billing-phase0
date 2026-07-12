# Phase 6 Wallet Ledger

Phase 6 adds account-level wallet accounting and an append-only ledger foundation. A wallet belongs to a subscriber account, not to a service, package, subscription, billing period, invoice, or payment provider transaction.

Phase 6 does not create payments, M-PESA, Paybill, Till, payment callbacks, invoices, receipts, renewal charges, automatic wallet-funded renewal, discounts, automatic expiry, suspension, RADIUS rows, PPPoE credentials, RouterOS calls, provisioning jobs, notifications, customer portals, installation fees, equipment billing, or live network actions.

## Data Model

`billing.Wallet` stores:

- UUID primary key
- protected one-to-one subscriber foreign key
- fixed `KES` currency
- creation timestamp

It does not store a mutable balance, payment reference, M-PESA transaction ID, invoice balance, service link, or package link. A subscriber may have no wallet row until the first ledger entry is posted. Viewing a subscriber without a wallet displays `KSh 0` without creating a database row.

`billing.LedgerEntry` stores:

- UUID primary key
- protected wallet foreign key
- per-wallet sequence number
- unique operation ID
- entry type: `manual_credit`, `manual_debit`, or `reversal`
- direction: `credit` or `debit`
- positive integer KES minor-unit amount
- non-negative integer KES minor-unit balance after the entry
- previous entry link
- optional reversed-entry link
- required trimmed reason, limited to 240 characters
- protected creating operator foreign key
- creation timestamp

There is no `updated_at` field on either model.

## Balance

Wallet balance is derived, not stored as a mutable field:

- no entries means `KSh 0`
- otherwise the balance is the latest ledger entry's `balance_after_minor`

All balances and amounts use integer KES minor units. Operators enter ordinary KSh values such as `500`, `1500`, or `1500.50`; conversion uses Decimal-safe money utilities.

Balances may not become negative.

## Manual Adjustments

Manual credits increase wallet balance but are not proof that money was received. They must not be described as M-PESA payments, Paybill payments, Till payments, receipts, or confirmed revenue.

Manual debits decrease wallet balance but are accounting corrections only. They are not package charges, renewal charges, invoices, receipts, or automatic service deductions.

Both workflows require:

- authenticated authorized operator
- operation ID
- positive KSh amount
- required reason
- audited service-layer mutation

## Reversals

Corrections use reversal entries rather than editing or deletion. A reversal:

- targets one manual credit or manual debit
- uses the exact original amount
- uses the opposite direction
- references the original entry
- can be created only once per original entry
- never modifies the original entry

A reversal that would make the wallet balance negative is rejected.

## Locking And Idempotency

Ledger mutations use `transaction.atomic()` and the lock order:

1. subscriber
2. wallet
3. latest ledger entry
4. reversal target, when applicable

The locked wallet and latest entry determine the next sequence, previous entry, current balance, and resulting balance. Database uniqueness remains the final concurrency guard.

Manual adjustments and reversals use operation IDs. Equivalent retries return the existing ledger entry and do not create a second audit event. Conflicting reuse of an operation ID raises validation errors without exposing raw database uniqueness errors.

PostgreSQL CI is authoritative for first-wallet creation, ledger sequence allocation, negative-balance prevention, duplicate operation handling, reversal races, and lock-order behavior. SQLite tests skip only true row-lock concurrency cases.

## Permissions

Viewing wallet data requires:

- `subscribers.view_subscriber`
- `billing.view_wallet`
- `billing.view_ledgerentry`

Posting a manual credit, manual debit, or reversal also requires:

- `billing.add_ledgerentry`

Owner receives all installed permissions. Administrator and Finance receive wallet and ledger view plus ledger add permissions. SuperSurf Support and Read Only receive wallet and ledger view permissions only. NOC receives no wallet or ledger permissions in Phase 6.

Ordinary roles do not receive `billing.add_wallet`, `billing.change_wallet`, `billing.delete_wallet`, `billing.change_ledgerentry`, or `billing.delete_ledgerentry`.

## Audit

Successful mutations record:

- `wallet.manual_credit`
- `wallet.manual_debit`
- `wallet.entry_reversed`

Audit metadata is limited to subscriber account number, wallet UUID, ledger-entry UUID, sequence number, entry type, direction, integer amount, integer balance after entry, currency, reversed entry UUID when present, and created timestamp.

Audit metadata must not contain operation IDs, raw POST payloads, phone numbers, email addresses, subscriber display names, payment claims, M-PESA information, credentials, or CSRF tokens.

## Admin

`Wallet` and `LedgerEntry` are registered read-only in Django admin. Admin add, change, delete, and bulk delete are disabled. The audited operator UI is the only supported application mutation path.

These are application-level controls. Privileged direct database writes remain outside application controls.
