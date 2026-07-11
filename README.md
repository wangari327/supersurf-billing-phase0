# SuperSurf Billing Phase 0

SuperSurf Billing is a planned Kenya-first ISP billing and subscriber-management platform for SuperSurf.

This repository now contains Phase 0 documentation, Phase 0.5 architectural corrections, and the Phase 1 lean Django foundation.

Phase 1 deliberately includes only `core`, `users`, and `audit` Django apps. It does not include M-PESA implementation, subscriber billing, wallets, ledger transactions, FreeRADIUS provisioning, PPPoE, RouterOS integration, or live network actions.

## Current Deliverables

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
- Django 5.2.16 LTS foundation
- SuperSurf and Kenya default seed migration
- Custom user model
- Staff roles using Django Groups and Permissions
- Append-only application audit model
- Operator shell pages
- Health and readiness endpoints
- Minimal Celery broker/worker wiring
- Docker Compose definitions for web, PostgreSQL, Valkey broker, worker, and scheduler
- GitHub Actions CI

## Phase Boundary

Phase 1 is complete as a foundation. Do not begin Phase 2 without explicit owner approval.

Disallowed in Phase 1 and still absent:

- M-PESA implementation
- Subscriber billing
- Wallets
- Ledger transactions
- FreeRADIUS provisioning
- PPPoE
- RouterOS integration
- Live network actions
- Production credentials
- Fake production domains, emails, Paybill numbers, Till numbers, or credentials

## Local Setup

Recommended setup uses `uv`:

```powershell
uv sync
npm ci --include=optional
npm run build:css
uv run python manage.py migrate
uv run python manage.py seed_roles
uv run python manage.py create_first_owner --username owner --email ""
uv run python manage.py runserver
```

If `uv` is not installed, see `docs/development/dependency-management.md`.

## Review Path

Start with:

1. `docs/product/supersurf-brand.md`
2. `docs/kenya/product-defaults.md`
3. `docs/architecture/overview.md`
4. `docs/reuse/component-research.md`
5. `docs/architecture/threat-model.md`
6. `docs/implementation/phase-1-checklist.md`
7. `docs/research/blocking-questions.md`
8. `docs/development/local-setup.md`
9. `docs/operations/first-owner.md`

## Production Readiness

This bundle does not claim KRA, VAT, eTIMS, Communications Authority, data protection, payment-processing, or network-compliance certification. Those require separate reviewed implementation, testing, and legal or regulatory review where applicable.

