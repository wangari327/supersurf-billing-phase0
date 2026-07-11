# Permission Matrix

SuperSurf uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Current permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change ordinary organization and branding settings, view/change users, assign non-Owner roles, view audit events, view/add/change packages, view/add/change subscribers, view/add/change services |
| Finance | View organization and branding, view audit events, view packages, view subscribers, view services |
| NOC | View organization and branding, view audit events, view packages, view subscribers, view services |
| SuperSurf Support | View organization and branding, view users, view packages, view subscribers, view services |
| Read Only | View organization, branding, users, audit events, packages, subscribers, and services |

Only an existing Owner may grant the Owner role, remove the Owner role, or modify another Owner's roles. Sensitive organization values such as KRA PIN, registration details, Paybill, Till, and licence information require `core.view_sensitive_settings` to display and `core.change_sensitive_settings` to change.

Ordinary roles do not receive `billing.delete_plan`, `subscribers.delete_subscriber`, or `subscribers.delete_service`. Packages, subscribers, and services are deactivated rather than deleted through normal workflows.

Subscriber profile visibility and service visibility are separate permission checks. `subscribers.view_subscriber` allows subscriber list and detail access; `subscribers.view_service` is required before service references, optional labels, statuses, lists, counts, service-reference search results, or dashboard service counts are shown. Service labels are optional, trimmed, and limited to 120 characters.

Later phases must refine these permissions before adding support tickets, subscriptions, payments, RADIUS, PPPoE credentials, RouterOS actions, or provisioning actions.
