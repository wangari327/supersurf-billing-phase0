# Phase 1 Implementation Checklist

Begin only after explicit owner approval.

## Foundation

- [ ] Create Django 5.2 LTS project.
- [ ] Configure reproducible dependency lockfile.
- [ ] Add PostgreSQL service.
- [ ] Add broker service after Redis/Valkey licence decision.
- [ ] Add Celery worker.
- [ ] Add scheduler.
- [ ] Add Caddy development reverse proxy configuration.
- [ ] Add `.env.example` with empty real-world values only.
- [ ] Configure local development on localhost ports.

## Core Settings And Branding

- [ ] Seed default organization as SuperSurf.
- [ ] Seed SuperSurf Billing product label.
- [ ] Seed SuperSurf Networks label.
- [ ] Seed SuperSurf Support label.
- [ ] Seed SuperSurf Portal label.
- [ ] Add organization settings UI.
- [ ] Support editable logo and favicon fields.
- [ ] Mark unset real-world fields as not configured.
- [ ] Block production activation when required settings are missing.

## Kenya Defaults

- [ ] Set Kenya, KE, KES, KSh, Africa/Nairobi, en-KE defaults.
- [ ] Store timestamps in UTC.
- [ ] Display dates as DD/MM/YYYY.
- [ ] Display times in 24-hour format.
- [ ] Format money as KSh while storing integer minor units.
- [ ] Add Kenya phone normalization service using maintained library.

## Users, Security, And RBAC

- [ ] Use Django auth.
- [ ] Add roles: Owner, Administrator, Finance, NOC, SuperSurf Support, Read Only.
- [ ] Add permission checks for privileged settings.
- [ ] Add login throttling.
- [ ] Add TOTP package spike and decision.
- [ ] Add secure cookie settings for production profile.
- [ ] Add secret redaction logging tests.
- [ ] Add session timeout settings.

## Audit

- [ ] Choose audit package after spike.
- [ ] Implement SuperSurf audit event model.
- [ ] Add redaction policy.
- [ ] Audit login, failed login, role changes, organization setting changes, exports, backup actions.
- [ ] Prevent logging secrets and sensitive identity values.

## UI

- [ ] Build restrained responsive operator shell.
- [ ] Add default navigation placeholders without implementing later-phase features.
- [ ] Add dashboard structure with real Phase 1 health/settings widgets only.
- [ ] Add accessible forms.
- [ ] Add base table, empty state, error state, and status badge patterns.

## CI And Quality

- [ ] Add pytest.
- [ ] Add pytest-django.
- [ ] Add factory-boy.
- [ ] Add Ruff.
- [ ] Add mypy where practical.
- [ ] Add dependency vulnerability scanning.
- [ ] Add licence/dependency reporting command.
- [ ] Add initial Playwright smoke test for login and dashboard.

## Documentation

- [ ] Update README with Phase 1 run commands.
- [ ] Update DEPENDENCIES.md with installed exact versions.
- [ ] Update THIRD_PARTY_NOTICES.md.
- [ ] Update SECURITY.md with implemented controls.
- [ ] Record unresolved risks.
- [ ] Stop for review before Phase 2.

