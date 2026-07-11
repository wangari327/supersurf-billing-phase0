# Dependency Policy And Phase 1 Shortlist

Phase 0 has not installed production dependencies. The packages below are shortlisted for Phase 1 validation and lockfile pinning.

Versions shown are current research targets from official documentation or registries accessed on 2026-07-11. Exact versions must be pinned during Phase 1 in a reproducible lockfile.

| Capability | Proposed dependency | Licence posture | Phase 1 stance |
| --- | --- | --- | --- |
| Web framework | Django 5.2.16 LTS target | BSD-3-Clause | Adopt unchanged |
| Database | PostgreSQL 18 if available in deployment base, otherwise supported 17 | PostgreSQL Licence | Adopt unchanged |
| PostgreSQL driver | psycopg 3.3.4 target | LGPL with exceptions or package-specific terms to review | Adopt unchanged after licence review |
| Cache and broker | Redis/Valkey decision pending; redis-py 8.0.1 target if Redis chosen | Redis server licence concerns require review; redis-py metadata shows MIT | Adopt only after licence review |
| Background jobs | Celery 5.6.3 target | BSD-3-Clause | Adopt unchanged |
| Scheduler | django-celery-beat 2.9.0 target | BSD | Adopt unchanged |
| Webhook/API layer | Django REST Framework 3.17.1 target | BSD | Use only for webhooks and versioned APIs |
| HTMX integration | django-htmx 1.27.0 target | Licence metadata to verify; package is permissive in project docs | Adopt unchanged |
| Filtering | django-filter 25.2 target | BSD | Adopt unchanged |
| Authentication | Django auth | BSD-3-Clause | Adopt unchanged |
| Login throttling | django-axes 8.3.1 target | MIT | Adopt behind local security policy |
| TOTP | django-otp 1.7.0 plus django-two-factor-auth 1.18.1 if UI is needed | Unlicense/MIT | Adopt behind local MFA service after review |
| Object permissions | django-guardian 3.3.2 or rules 3.5 | BSD-2-Clause/MIT | Evaluate in Phase 1 spike |
| Audit history | django-simple-history 3.12.0 or django-auditlog 3.4.1 | BSD/MIT | Evaluate in Phase 1 spike |
| Phone numbers | phonenumbers 9.0.34 plus django-phonenumber-field 8.4.0 | Apache-2.0-style/MIT | Adopt behind PhoneNumberNormalizer |
| Money formatting | Babel 2.18.0 plus integer minor units | BSD-3-Clause | Adopt unchanged; do not use floats |
| Money fields | django-money 3.6.1 | BSD | Evaluate; may use only at presentation/model boundary |
| HTTP client | httpx 0.28.1 | BSD-3-Clause | Adopt behind integration clients |
| Retry | tenacity 9.1.4 | Apache-2.0 | Adopt behind integrations |
| Structured logging | structlog 26.1.0 and django-structlog 10.1.0 | Apache-2.0/MIT and MIT | Adopt unchanged |
| Health checks | django-health-check 4.4.3 or custom thin endpoint | MIT | Evaluate |
| CSV import/export | Python csv, tablib 3.9.0, or django-import-export 4.4.1 | PSF/MIT/BSD | Evaluate for admin imports; custom mapping for statements |
| Testing | pytest 9.1.1, pytest-django 4.12.0, factory-boy 3.3.3, Playwright 1.61.0 | MIT/BSD/Apache review needed | Adopt unchanged |
| Linting | Ruff 0.15.21 | MIT | Adopt unchanged |
| Typing | mypy 2.2.0 | MIT | Adopt where practical |
| RouterOS API | librouteros 4.1.1 or routeros-api 0.21.0 | librouteros metadata unclear; routeros-api MIT | Adopt behind RouterOSAdapter only if licence suitable |
| RADIUS client | pyrad 2.5.4 | BSD-3-Clause | Adopt behind RadiusCoaClient if CoA support tests pass |
| FreeRADIUS SQL | Official FreeRADIUS PostgreSQL schema | GPL project; schema use must be reviewed | Use official schema as integration boundary after licence review |
| Reverse proxy | Caddy 2 | Apache-2.0 | Adopt unchanged for automatic HTTPS |

## Not Yet Adopted

No dependency is formally adopted until Phase 1 validates:

- Current stable version
- Licence compatibility
- Django 5.2 LTS compatibility
- PostgreSQL support
- Maintenance status
- Test evidence
- Security posture
- Dependency weight
