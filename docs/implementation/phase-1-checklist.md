# Phase 1 Implementation Checklist

Begin only after the Phase 0.5 documentation correction commit is complete.

Phase 1 is a lean foundation only. Do not create Phase 2 domain models such as `Payment`, `Wallet`, `LedgerEntry`, `Subscriber`, `Plan`, `Subscription`, `RadiusAccount`, `NASRouter`, or `ProvisioningJob`.

## Foundation

- [ ] Use Python 3.13 unless a verified dependency requires another supported version.
- [ ] Create Django 5.2.16 LTS project.
- [ ] Use uv for dependency management unless a documented compatibility problem exists.
- [ ] Configure a reproducible dependency lockfile.
- [ ] Add PostgreSQL 17 service.
- [ ] Add broker service after Redis/Valkey compatibility and licence review.
- [ ] Add minimal Celery worker and scheduler only for infrastructure health.
- [ ] Keep Caddy optional, not required for localhost development.
- [ ] Add `.env.example` with empty real-world values only.
- [ ] Configure local development on localhost ports.

## Allowed Django Apps

- [ ] Create `core`.
- [ ] Create `users`.
- [ ] Create `audit`.
- [ ] Do not create empty `subscribers`, `billing`, `payments`, `network`, or `support` apps.

## Core Settings And Branding

- [ ] Implement Organization model for the one SuperSurf organization.
- [ ] Implement OrganizationBranding model or equivalent focused settings model.
- [ ] Seed primary brand as SuperSurf.
- [ ] Seed product name as SuperSurf Billing.
- [ ] Seed network label as SuperSurf Networks.
- [ ] Seed support label as SuperSurf Support.
- [ ] Seed portal label as SuperSurf Portal.
- [ ] Seed Kenya, KE, KES, KSh, Africa/Nairobi, en-KE, DD/MM/YYYY, 24-hour time, Monday week start, +254.
- [ ] Provide editable but empty real-world fields: registered business name, domain, support email, billing email, NOC email, support phone, Paybill number, Till number, KRA PIN, registration number, Communications Authority licence information.
- [ ] Mark unset real-world fields as not configured.
- [ ] Protect sensitive or privileged settings by role.
- [ ] Add health endpoint.
- [ ] Add readiness endpoint.
- [ ] Add environment banner: DEVELOPMENT, TEST, LAB, or PRODUCTION.
- [ ] Add production-readiness checks.

## Users, Security, And RBAC

- [ ] Use a custom Django user model from the first migration.
- [ ] Use Django built-in authentication, Groups, and Permissions.
- [ ] Do not install django-guardian, rules, or django-role-permissions in Phase 1 unless proven necessary.
- [ ] Add roles: Owner, Administrator, Finance, NOC, SuperSurf Support, Read Only.
- [ ] Add a management command to seed groups and permissions.
- [ ] Do not automatically create an owner password.
- [ ] Add a documented command for creating the first owner.
- [ ] Implement login, logout, and password change.
- [ ] Add session expiry.
- [ ] Add login throttling.
- [ ] Add privileged role checks.
- [ ] Evaluate django-otp for optional TOTP.
- [ ] Do not install django-two-factor-auth unless django-otp alone cannot satisfy the approved workflow.
- [ ] Invalidate sessions after critical role changes where practical.

## Audit

- [ ] Prefer one explicit SuperSurf AuditEvent model and service.
- [ ] Do not install django-simple-history, django-auditlog, and django-reversion together.
- [ ] Capture actor, action, target type, target identifier, request correlation ID, timestamp, safe metadata, source IP where appropriate, result, and privileged-action reason.
- [ ] Do not place secrets or full sensitive values in metadata.
- [ ] Avoid ordinary update/delete operations for AuditEvent in application code.
- [ ] Do not claim cryptographic immutability.
- [ ] Audit successful login, failed login where safely identifiable, logout, password change, role changes, organization-setting changes, branding changes, and production-readiness override attempts.
- [ ] Do not rely only on Django signals for important audit events.

## UI

- [ ] Build a clean responsive SuperSurf operator shell.
- [ ] Add login page.
- [ ] Add dashboard.
- [ ] Add SuperSurf settings page.
- [ ] Add staff list.
- [ ] Add staff detail.
- [ ] Add role assignment.
- [ ] Add audit log.
- [ ] Add system health page.
- [ ] Do not create dead links for later modules.
- [ ] Put later features only under a clearly labelled "Coming later" section.
- [ ] Add accessible forms, keyboard-visible focus states, tables, empty states, error states, success messages, status badges, pagination, staff search, and audit search.

## Celery And Broker

- [ ] Prove worker starts.
- [ ] Prove scheduler starts if included.
- [ ] Prove broker connectivity works.
- [ ] Add one harmless health task.
- [ ] Make worker failure visible.
- [ ] Test Valkey compatibility with selected Celery and redis-py versions.
- [ ] Use Valkey if compatibility passes cleanly; otherwise document reason and use reviewed Redis.
- [ ] Do not create payment, renewal, suspension, RouterOS, or RADIUS tasks.

## Docker Compose

- [ ] Provide web service.
- [ ] Provide postgres service.
- [ ] Provide broker service.
- [ ] Provide worker service.
- [ ] Provide scheduler service if included.
- [ ] Keep Caddy optional.
- [ ] Add health checks.
- [ ] Add persistent PostgreSQL volume.
- [ ] Use non-root application container where practical.
- [ ] Add startup dependency handling.
- [ ] Keep real secrets out of Compose files.

## Tests And Quality

- [ ] Test SuperSurf seed defaults.
- [ ] Test Kenya defaults.
- [ ] Test custom user model.
- [ ] Test group and permission seeding.
- [ ] Test unauthorized settings access.
- [ ] Test role-change authorization.
- [ ] Test audit-event creation.
- [ ] Test audit redaction.
- [ ] Test login throttling.
- [ ] Test session behavior.
- [ ] Test health endpoint.
- [ ] Test readiness endpoint.
- [ ] Test missing production settings.
- [ ] Test no invented domain or email values.
- [ ] Test no secret values in logs.
- [ ] Test dashboard access.
- [ ] Add Playwright login and dashboard smoke flow.
- [ ] Run pytest.
- [ ] Run Ruff.
- [ ] Run mypy.
- [ ] Run Django system checks.
- [ ] Run Django deployment checks against production settings.
- [ ] Run dependency vulnerability scan.
- [ ] Run licence report.
- [ ] Run Docker Compose config validation where Docker Compose is available.

## CI

- [ ] Install dependencies from lockfile.
- [ ] Run Ruff.
- [ ] Run mypy.
- [ ] Run pytest.
- [ ] Run Django checks.
- [ ] Run secret scanning.
- [ ] Run dependency vulnerability scanning.
- [ ] Require no production credentials in CI.

## Documentation

- [ ] Update README.
- [ ] Update AGENTS.md.
- [ ] Update DEPENDENCIES.md.
- [ ] Update THIRD_PARTY_NOTICES.md.
- [ ] Update SECURITY.md.
- [ ] Update `docs/reuse/decision-log.md`.
- [ ] Create `docs/development/local-setup.md`.
- [ ] Create `docs/development/testing.md`.
- [ ] Create `docs/development/dependency-management.md`.
- [ ] Create `docs/operations/first-owner.md`.
- [ ] Create `docs/operations/environment-profiles.md`.
- [ ] Stop for review before Phase 2.

