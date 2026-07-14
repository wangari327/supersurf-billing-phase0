# Permission Matrix

SuperSurf uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Current permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change ordinary organization and branding settings, view/change users, assign non-Owner roles, view audit events, view/add/change packages, view/add/change subscriptions, view/add billing periods, view/add billing charges, view wallets, view/add ledger entries, view/add payment provider profiles, view/add payments, view/add payment allocations, view/change unmatched payment cases, view M-PESA callback evidence, view/add/change subscribers, view/add/change services |
| Finance | View organization and branding, view audit events, view packages, view subscriptions, view/add billing periods, view/add billing charges, view wallets, view/add ledger entries, view/add payment provider profiles, view/add payments, view/add payment allocations, view/change unmatched payment cases, view M-PESA callback evidence, view subscribers, view services |
| NOC | View organization and branding, view audit events, view packages, view subscriptions, view billing periods, view subscribers, view services |
| SuperSurf Support | View organization and branding, view users, view packages, view subscriptions, view billing periods, view billing charges, view wallets, view ledger entries, view payments, view payment allocations, view unmatched payment cases, view subscribers, view services |
| Read Only | View organization, branding, users, audit events, packages, subscriptions, billing periods, billing charges, wallets, ledger entries, payments, payment allocations, unmatched payment cases, subscribers, and services |

Only an existing Owner may grant the Owner role, remove the Owner role, or modify another Owner's roles. Sensitive organization values such as KRA PIN, registration details, Paybill, Till, and licence information require `core.view_sensitive_settings` to display and `core.change_sensitive_settings` to change.

Ordinary roles do not receive `billing.delete_plan`, `billing.delete_subscription`, `billing.change_billingperiod`, `billing.delete_billingperiod`, `billing.change_billingcharge`, `billing.delete_billingcharge`, `billing.add_wallet`, `billing.change_wallet`, `billing.delete_wallet`, `billing.change_ledgerentry`, `billing.delete_ledgerentry`, `billing.change_payment`, `billing.delete_payment`, `billing.change_paymentallocation`, `billing.delete_paymentallocation`, `billing.delete_unmatchedpaymentcase`, `billing.add_mpesacallbackevent`, `billing.change_mpesacallbackevent`, `billing.delete_mpesacallbackevent`, `subscribers.delete_subscriber`, or `subscribers.delete_service`. Packages, subscribers, and services are deactivated rather than deleted through normal workflows. Subscriptions are ended rather than deleted. Billing periods, billing charges, ledger entries, payments, payment allocations, and M-PESA callback events are append-only and have no edit or delete workflow.

Subscriber profile visibility and service visibility are separate permission checks. `subscribers.view_subscriber` allows subscriber list and detail access; `subscribers.view_service` is required before service references, optional labels, statuses, lists, counts, service-reference search results, or dashboard service counts are shown. Service labels are optional, trimmed, and limited to 120 characters.

Subscription information on subscriber pages requires both `subscribers.view_service` and `billing.view_subscription`. Assigning a first package requires `billing.add_subscription`; changing or ending an active subscription requires `billing.change_subscription`.

Billing period information requires `subscribers.view_service`, `billing.view_subscription`, and `billing.view_billingperiod`. Creating a manual activation or renewal requires `subscribers.view_service`, `billing.view_subscription`, and `billing.add_billingperiod`. Manual renewal does not claim payment receipt and does not grant any network enforcement authority.

Wallet information requires `subscribers.view_subscriber`, `billing.view_wallet`, and `billing.view_ledgerentry`. Posting manual wallet credits, manual debits, or reversals also requires `billing.add_ledgerentry`. NOC has no wallet, ledger, billing-charge, payment, allocation, or unmatched-payment permissions in Phase 8. Manual wallet credits do not confirm receipt of payment, and manual debits are not package charges or invoices.

Wallet-funded activation and renewal require the billing-period permissions plus `billing.view_wallet`, `billing.view_ledgerentry`, `billing.add_ledgerentry`, `billing.view_billingcharge`, and `billing.add_billingcharge`. Administrator and Finance can post Wallet-funded charges. SuperSurf Support and Read Only can view charge status only where they also have the supporting service, subscription, billing-period, Wallet, and ledger view permissions.

`billing.view_payment` allows payment list/detail access, payment-owned fields, and derived allocated/unmatched state. Allocation destination details require all of `billing.view_paymentallocation`, `billing.view_wallet`, `billing.view_ledgerentry`, and `subscribers.view_subscriber`. Searching payments through allocated subscriber account numbers requires `billing.view_paymentallocation` and `subscribers.view_subscriber`.

Unmatched case details require `billing.view_unmatchedpaymentcase`. The unmatched payment list requires both `billing.view_unmatchedpaymentcase` and `billing.view_payment` because it displays payment-owned fields.

Fake payment ingestion requires Administrator or Finance permissions for subscriber viewing, payment provider profile viewing, payment add/view, payment allocation add/view, Wallet and ledger viewing, and ledger-entry creation. Unmatched-payment resolution additionally requires unmatched-case view/change permissions and an explicit resolution reason. SuperSurf Support and Read Only can view payments, payment allocations, and unmatched payment cases because they have the supporting view permissions, but cannot ingest fake payments or resolve cases. NOC has no payment visibility.

`billing.view_mpesacallbackevent` allows read-only access to Daraja callback evidence list/detail pages and sanitized payload display. Administrator and Finance receive this permission; Support, Read Only, and NOC do not. No ordinary role can add, change, or delete callback events through operator interfaces.

Later phases must refine these permissions before adding support tickets, real Paybill or Till provider adapters that create payments, invoices, receipts, RADIUS, PPPoE credentials, RouterOS actions, or provisioning actions.
