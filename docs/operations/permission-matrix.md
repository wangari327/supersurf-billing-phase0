# Phase 1 Permission Matrix

Phase 1 uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Phase 1 permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change ordinary organization and branding settings, view/change users, assign non-Owner roles, view audit events |
| Finance | View organization and branding, view audit events |
| NOC | View organization and branding, view audit events |
| SuperSurf Support | View organization and branding, view users |
| Read Only | View organization, branding, users, and audit events |

Only an existing Owner may grant the Owner role, remove the Owner role, or modify another Owner's roles. Sensitive organization values such as KRA PIN, registration details, Paybill, Till, and licence information require `core.view_sensitive_settings` to display and `core.change_sensitive_settings` to change.

Later phases must refine these permissions before adding payments, subscriber records, support tickets, RADIUS, or RouterOS actions.
