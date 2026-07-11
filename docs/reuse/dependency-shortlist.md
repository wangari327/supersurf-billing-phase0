# Phase 1 Dependency Shortlist

This is a candidate list, not an installed lockfile.

## Adopt In Phase 1 Unless Validation Fails

- Django 5.2.16 LTS target
- psycopg 3.3.4 target
- PostgreSQL official image, pinned to a supported major version
- Celery 5.6.3 target
- django-celery-beat 2.9.0 target
- django-htmx 1.27.0 target
- django-filter 25.2 target
- django-environ 0.14.0 target
- django-axes 8.3.1 target
- django-otp 1.7.0 target
- structlog 26.1.0 target
- django-structlog 10.1.0 target
- pytest 9.1.1 target
- pytest-django 4.12.0 target
- factory-boy 3.3.3 target
- Ruff 0.15.21 target
- mypy 2.2.0 target
- Playwright 1.61.0 target
- Caddy 2 official image, pinned

Phase 0.5 correction: this list is a research shortlist. Phase 1 implementation should install only what is needed for the lean foundation. Do not install DRF, payment, RouterOS, RADIUS, phone-number, money, accounting, ledger, reconciliation, or statement-import dependencies until the relevant later phase requires them.

## Evaluate In Phase 1 Spikes

- django-guardian 3.3.2 versus rules 3.5 for permissions
- django-two-factor-auth 1.18.1 for TOTP UI flows
- django-simple-history 3.12.0 versus django-auditlog 3.4.1 for audit support
- django-money 3.6.1 for money fields versus internal integer fields plus Babel formatting
- django-health-check 4.4.3 versus thin custom health/readiness endpoints
- Redis 8/redis-py 8.0.1 versus Valkey depending licence and deployment posture

## Defer To Later Phases

- librouteros 4.1.1
- routeros-api 0.21.0
- pyrad 2.5.4
- FreeRADIUS server package/image
- django-import-export 4.4.1
- tablib 3.9.0

## Reject For MVP

- django-daraja 1.3.0 unless sandbox proof shows current compatibility
- python-daraja 1.2.4
- mpesa-sdk 1.0.7
- django-freeradius 0.1
- Full accounting packages as primary ledger implementation
