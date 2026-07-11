# Phase 1 Implementation Checklist

Begin only after the Phase 0.5 documentation correction commit is complete.

Phase 1 is a lean foundation only. Do not create Phase 2 domain models such as `Payment`, `Wallet`, `LedgerEntry`, `Subscriber`, `Plan`, `Subscription`, `RadiusAccount`, `NASRouter`, or `ProvisioningJob`.

## Foundation

- [x] Use Python 3.13 unless a verified dependency requires another supported version.
- [x] Create Django 5.2.16 LTS project.
- [x] Use uv for dependency management unless a documented compatibility problem exists.
- [x] Configure a reproducible dependency lockfile.
- [x] Add PostgreSQL 17 service.
- [x] Add broker service after Redis/Valkey compatibility and licence review.
- [x] Add minimal Celery worker and scheduler only for infrastructure health.
- [x] Keep Caddy optional, not required for localhost development.
- [x] Add `.env.example` with empty real-world values only.
- [x] Configure local development on localhost ports.

## Allowed Django Apps

- [x] Create `core`.
- [x] Create `users`.
- [x] Create `audit`.
- [x] Do not create empty `subscribers`, `billing`, `payments`, `network`, or `support` apps.

## Core Settings And Branding

- [x] Implement Organization model for the one SuperSurf organization.
- [x] Implement OrganizationBranding model or equivalent focused settings model.
- [x] Seed primary brand as SuperSurf.
- [x] Seed product name as SuperSurf Billing.
- [x] Seed network label as SuperSurf Networks.
- [x] Seed support label as SuperSurf Support.
- [x] Seed portal label as SuperSurf Portal.
- [x] Seed Kenya, KE, KES, KSh, Africa/Nairobi, en-KE, DD/MM/YYYY, 24-hour time, Monday week start, +254.
- [x] Provide editable but empty real-world fields: registered business name, domain, support email, billing email, NOC email, support phone, Paybill number, Till number, KRA PIN, registration number, Communications Authority licence information.
- [x] Mark unset real-world fields as not configured.
- [x] Protect sensitive or privileged settings by role.
- [x] Add health endpoint.
- [x] Add readiness endpoint.
- [x] Add environment banner: DEVELOPMENT, TEST, LAB, or PRODUCTION.
- [x] Add production-readiness checks.

## Users, Security, And RBAC

- [x] Use a custom Django user model from the first migration.
- [x] Use Django built-in authentication, Groups, and Permissions.
- [x] Do not install django-guardian, rules, or django-role-permissions in Phase 1 unless proven necessary.
- [x] Add roles: Owner, Administrator, Finance, NOC, SuperSurf Support, Read Only.
- [x] Add a management command to seed groups and permissions.
- [x] Do not automatically create an owner password.
- [x] Add a documented command for creating the first owner.
- [x] Implement login, logout, and password change.
- [x] Add session expiry.
- [x] Add login throttling.
- [x] Add privileged role checks.
- [x] Evaluate django-otp for optional TOTP.
- [x] Do not install django-two-factor-auth unless django-otp alone cannot satisfy the approved workflow.
- [x] Invalidate sessions after critical role changes where practical.

## Audit

- [x] Prefer one explicit SuperSurf AuditEvent model and service.
- [x] Do not install django-simple-history, django-auditlog, and django-reversion together.
- [x] Capture actor, action, target type, target identifier, request correlation ID, timestamp, safe metadata, source IP where appropriate, result, and privileged-action reason.
- [x] Do not place secrets or full sensitive values in metadata.
- [x] Avoid ordinary update/delete operations for AuditEvent in application code.
- [x] Do not claim cryptographic immutability.
- [x] Audit successful login, failed login where safely identifiable, logout, password change, role changes, organization-setting changes, branding changes, and production-readiness override attempts.
- [x] Do not rely only on Django signals for important audit events.

## UI

- [x] Build a clean responsive SuperSurf operator shell.
- [x] Add login page.
- [x] Add dashboard.
- [x] Add SuperSurf settings page.
- [x] Add staff list.
- [x] Add staff detail.
- [x] Add role assignment.
- [x] Add audit log.
- [x] Add system health page.
- [x] Do not create dead links for later modules.
- [x] Put later features only under a clearly labelled "Coming later" section.
- [x] Add accessible forms, keyboard-visible focus states, tables, empty states, error states, success messages, status badges, pagination, staff search, and audit search.

## Celery And Broker

- [ ] Prove worker starts. Blocked locally by unavailable Docker daemon/Compose; CI configuration is present.
- [ ] Prove scheduler starts if included. Blocked locally by unavailable Docker daemon/Compose; CI configuration is present.
- [ ] Prove broker connectivity works. Blocked locally by unavailable Docker daemon; redis-py/Celery dependency compatibility resolves.
- [x] Add one harmless health task.
- [x] Make worker failure visible through Compose service health/logs design.
- [ ] Test Valkey runtime compatibility with selected Celery and redis-py versions. Blocked locally by unavailable Docker daemon.
- [x] Use Valkey if compatibility passes cleanly; otherwise document reason and use reviewed Redis.
- [x] Do not create payment, renewal, suspension, RouterOS, or RADIUS tasks.

## Docker Compose

- [x] Provide web service.
- [x] Provide postgres service.
- [x] Provide broker service.
- [x] Provide worker service.
- [x] Provide scheduler service if included.
- [x] Keep Caddy optional.
- [x] Add health checks.
- [x] Add persistent PostgreSQL volume.
- [x] Use non-root application container where practical.
- [x] Add startup dependency handling.
- [x] Keep real secrets out of Compose files.

## Tests And Quality

- [x] Test SuperSurf seed defaults.
- [x] Test Kenya defaults.
- [x] Test custom user model.
- [x] Test group and permission seeding.
- [x] Test unauthorized settings access.
- [x] Test role-change authorization.
- [x] Test audit-event creation.
- [x] Test audit redaction.
- [x] Test login throttling.
- [x] Test session behavior.
- [x] Test health endpoint.
- [x] Test readiness endpoint.
- [x] Test missing production settings.
- [x] Test no invented domain or email values.
- [x] Test no secret values in logs.
- [x] Test dashboard access.
- [x] Add Playwright login and dashboard smoke flow.
- [x] Run pytest.
- [x] Run Ruff.
- [x] Run mypy.
- [x] Run Django system checks.
- [x] Run Django deployment checks against production settings.
- [x] Run dependency vulnerability scan.
- [x] Run licence report.
- [ ] Run Docker Compose config validation where Docker Compose is available. Blocked locally because Docker Compose is not installed.

## CI

- [x] Install dependencies from lockfile.
- [x] Run Ruff.
- [x] Run mypy.
- [x] Run pytest.
- [x] Run Django checks.
- [x] Run secret scanning.
- [x] Run dependency vulnerability scanning.
- [x] Require no production credentials in CI.

## Documentation

- [x] Update README.
- [x] Update AGENTS.md.
- [x] Update DEPENDENCIES.md.
- [x] Update THIRD_PARTY_NOTICES.md.
- [x] Update SECURITY.md.
- [x] Update `docs/reuse/decision-log.md`.
- [x] Create `docs/development/local-setup.md`.
- [x] Create `docs/development/testing.md`.
- [x] Create `docs/development/dependency-management.md`.
- [x] Create `docs/operations/first-owner.md`.
- [x] Create `docs/operations/environment-profiles.md`.
- [x] Stop for review before Phase 2.
