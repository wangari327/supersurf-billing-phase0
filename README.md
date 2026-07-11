# SuperSurf Billing Phase 0

SuperSurf Billing is a planned Kenya-first ISP billing and subscriber-management platform for SuperSurf.

This repository bundle contains Phase 0 only. It is intentionally documentation-first and does not include a production Django scaffold, production database migrations, live router integration, production credentials, or generated RouterOS scripts.

## Phase 0 Deliverables

- SuperSurf product and brand contract
- Kenya-specific defaults and subscriber data conventions
- Official documentation research
- Open-source and package reconnaissance
- Reuse and dependency shortlist
- Licence review and third-party notices
- Proposed modular-monolith architecture
- Entity-relationship model
- Paybill and Till workflows
- FreeRADIUS and MikroTik integration design
- Network safety model
- Threat model and permission model
- Backup design
- ADRs for the initial technical direction
- Phase 1 implementation checklist
- Genuine blocking questions

## Phase 0 Boundary

Phase 0 stops before implementation. Do not create production application code from this bundle without explicit approval to begin Phase 1.

Allowed Phase 0 artifacts:

- Markdown documentation
- Architecture diagrams
- Research notes
- Reuse decisions
- ADRs
- Optional disposable spikes under `spikes/`

Disallowed in Phase 0:

- Production Django application scaffold
- Production database migrations
- Production M-PESA credentials
- Production router credentials
- Live SuperSurf L009 access
- Automatically executed RouterOS scripts
- Fake production domains, emails, Paybill numbers, Till numbers, or credentials

## Review Path

Start with:

1. `docs/product/supersurf-brand.md`
2. `docs/kenya/product-defaults.md`
3. `docs/architecture/overview.md`
4. `docs/reuse/component-research.md`
5. `docs/architecture/threat-model.md`
6. `docs/implementation/phase-1-checklist.md`
7. `docs/research/blocking-questions.md`

## Production Readiness

This bundle does not claim KRA, VAT, eTIMS, Communications Authority, data protection, payment-processing, or network-compliance certification. Those require separate reviewed implementation, testing, and legal or regulatory review where applicable.

