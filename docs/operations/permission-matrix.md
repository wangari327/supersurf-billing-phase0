# Phase 1 Permission Matrix

Phase 1 uses Django Groups and Permissions. Run `python manage.py seed_roles` after migrations.

| Role | Phase 1 permissions |
| --- | --- |
| Owner | All installed Django permissions |
| Administrator | View/change organization and branding, view sensitive settings, view/change users, assign roles, view audit events |
| Finance | View organization and branding, view audit events |
| NOC | View organization and branding, view audit events |
| SuperSurf Support | View organization and branding, view users |
| Read Only | View organization, branding, users, and audit events |

Later phases must refine these permissions before adding payments, subscriber records, support tickets, RADIUS, or RouterOS actions.

