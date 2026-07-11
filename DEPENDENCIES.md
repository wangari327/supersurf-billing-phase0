# Dependency Policy And Phase 1 Shortlist

Phase 1 installed only foundation dependencies. Exact versions are pinned in `uv.lock` and `package-lock.json`.

| Capability | Proposed dependency | Licence posture | Phase 1 stance |
| --- | --- | --- | --- |
| Web framework | Django 5.2.16 | BSD-3-Clause | Installed |
| Database | PostgreSQL 17 image | PostgreSQL Licence | Compose target |
| PostgreSQL driver | psycopg 3.3.4 with binary extra | LGPL with exceptions | Installed |
| Broker | Valkey 8 image | BSD-3-Clause | Compose target; local daemon check blocked |
| Broker client | redis-py 6.4.0 | MIT | Installed; selected because Celery/Kombu 5.6 rejects redis-py 8.x |
| Background jobs | Celery 5.6.3 | BSD-3-Clause | Installed for infrastructure health only |
| HTMX integration | django-htmx 1.27.0 | MIT | Installed |
| Authentication | Django auth | BSD-3-Clause | Adopt unchanged |
| Login throttling | django-axes 8.3.1 | MIT | Installed after compatibility check |
| Optional TOTP foundation | django-otp 1.7.0 | Unlicense | Installed; no django-two-factor-auth |
| Testing | pytest 9.1.1, pytest-django 4.12.0, Playwright 1.61.0 | MIT/BSD/Apache | Installed |
| Linting | Ruff 0.15.21 | MIT | Installed |
| Typing | mypy 2.2.0 | MIT | Installed |
| Vulnerability scan | pip-audit 2.10.1 | Apache-2.0 | Installed |
| Licence report | pip-licenses 5.5.5 | MIT | Installed |
| CSS build | Tailwind CSS 4.1.17 and @tailwindcss/cli 4.1.17 | MIT | Installed via npm |
| Optional reverse proxy | Caddy 2 image | Apache-2.0 | Optional Compose profile only |

## Not Yet Adopted

## Explicitly Not Installed In Phase 1

- Django REST Framework
- django-guardian
- rules
- django-role-permissions
- django-two-factor-auth
- django-simple-history
- django-auditlog
- django-reversion
- django-money
- django-ledger
- django-hordak
- phonenumbers
- django-phonenumber-field
- M-PESA packages
- RouterOS packages
- RADIUS client packages
- FreeRADIUS packages
