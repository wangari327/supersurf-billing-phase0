# Open-Source ISP And RADIUS Systems

The purpose of this review is to learn from existing systems and identify reusable components, not to fork an entire billing platform.

## Projects Examined

| Project | Source | Category | Licence posture | Classification | Reason |
| --- | --- | --- | --- | --- | --- |
| FreeRADIUS | https://github.com/FreeRADIUS/freeradius-server | RADIUS server | GPL project | Adopt as external system | Mature RADIUS server with SQL authorization/accounting support. Do not copy code into SuperSurf. |
| daloRADIUS | https://github.com/lirantal/daloradius | FreeRADIUS web management | GPL-style to verify | Architecture reference only | Useful operational reference for RADIUS tables and admin workflows, but not a Django billing foundation. |
| RADIUSdesk | https://github.com/RADIUSdesk/rdcore | RADIUS/hotspot/mesh management | GPL/AGPL posture to verify | Architecture reference only | Useful UI and workflow reference; licence and scope unsuitable for direct adoption. |
| OpenWISP | https://github.com/openwisp | Network management | BSD/GPL mix by package, verify | Architecture reference; possible selective dependency later | Strong network-management project, but broader than SuperSurf Billing MVP. |
| OpenWISP RADIUS | https://github.com/openwisp/openwisp-radius | RADIUS user management | Verify package licence | Architecture reference | Useful for RADIUS user and accounting patterns; not adopted in Phase 0. |
| LibreQoS | https://github.com/LibreQoE/LibreQoS | QoE/QoS monitoring | Licence to verify | Reject for MVP | Useful for future QoE thinking, not required for billing MVP. |
| ISPConfig | https://www.ispconfig.org/ | Hosting control panel | BSD/GPL mix to verify | Reject | Not an ISP subscriber billing platform. |
| Commercial ISP billing tools | Vendor websites | Billing/BSS | Proprietary | Reject | Can inspire requirements, but do not copy code, templates, schemas, or proprietary workflows. |

## Patterns To Reuse Conceptually

- Separate RADIUS operational tables from business-domain tables.
- Keep accounting records append-only.
- Show active sessions and accounting summaries to NOC.
- Keep manual payment resolution auditable.
- Avoid using router state as the billing source of truth.
- Provide dry-run and lab validation before network writes.

