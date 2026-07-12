# Permission Matrix

SuperSurf uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Current permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change ordinary organization and branding settings, view/change users, assign non-Owner roles, view audit events, view/add/change packages, view/add/change subscriptions, view/add billing periods, view/add/change subscribers, view/add/change services |
| Finance | View organization and branding, view audit events, view packages, view subscriptions, view/add billing periods, view subscribers, view services |
| NOC | View organization and branding, view audit events, view packages, view subscriptions, view billing periods, view subscribers, view services |
| SuperSurf Support | View organization and branding, view users, view packages, view subscriptions, view billing periods, view subscribers, view services |
| Read Only | View organization, branding, users, audit events, packages, subscriptions, billing periods, subscribers, and services |

Only an existing Owner may grant the Owner role, remove the Owner role, or modify another Owner's roles. Sensitive organization values such as KRA PIN, registration details, Paybill, Till, and licence information require `core.view_sensitive_settings` to display and `core.change_sensitive_settings` to change.

Ordinary roles do not receive `billing.delete_plan`, `billing.delete_subscription`, `billing.change_billingperiod`, `billing.delete_billingperiod`, `subscribers.delete_subscriber`, or `subscribers.delete_service`. Packages, subscribers, and services are deactivated rather than deleted through normal workflows. Subscriptions are ended rather than deleted. Billing periods are append-only and have no edit or delete workflow.

Subscriber profile visibility and service visibility are separate permission checks. `subscribers.view_subscriber` allows subscriber list and detail access; `subscribers.view_service` is required before service references, optional labels, statuses, lists, counts, service-reference search results, or dashboard service counts are shown. Service labels are optional, trimmed, and limited to 120 characters.

Subscription information on subscriber pages requires both `subscribers.view_service` and `billing.view_subscription`. Assigning a first package requires `billing.add_subscription`; changing or ending an active subscription requires `billing.change_subscription`.

Billing period information requires `subscribers.view_service`, `billing.view_subscription`, and `billing.view_billingperiod`. Creating a manual activation or renewal requires `subscribers.view_service`, `billing.view_subscription`, and `billing.add_billingperiod`. Manual renewal does not claim payment receipt and does not grant any network enforcement authority.

Later phases must refine these permissions before adding support tickets, payments, wallets, ledgers, invoices, RADIUS, PPPoE credentials, RouterOS actions, or provisioning actions.
