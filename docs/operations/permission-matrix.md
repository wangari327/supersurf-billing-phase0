# Permission Matrix

SuperSurf uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Current permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change ordinary organization and branding settings, view/change users, assign non-Owner roles, view audit events, view/add/change packages |
| Finance | View organization and branding, view audit events, view packages |
| NOC | View organization and branding, view audit events, view packages |
| SuperSurf Support | View organization and branding, view users, view packages |
| Read Only | View organization, branding, users, audit events, and packages |

Only an existing Owner may grant the Owner role, remove the Owner role, or modify another Owner's roles. Sensitive organization values such as KRA PIN, registration details, Paybill, Till, and licence information require `core.view_sensitive_settings` to display and `core.change_sensitive_settings` to change.

Ordinary roles do not receive `billing.delete_plan`; packages are deactivated rather than deleted.

Later phases must refine these permissions before adding subscriber records, support tickets, payments, RADIUS, or RouterOS actions.
