# Third-Party Notices

No production third-party source code has been copied into this repository.

This file records installed Phase 1 dependencies and remaining reference sources. See `docs/reuse/phase-1-licence-report.md` for the generated package licence report.

## Candidate Components

| Component | Source | Licence posture | Current use |
| --- | --- | --- | --- |
| Django | https://www.djangoproject.com/ | BSD-3-Clause | Installed |
| PostgreSQL | https://www.postgresql.org/ | PostgreSQL Licence | Compose target |
| Celery | https://docs.celeryq.dev/ | BSD | Installed |
| Valkey | https://valkey.io/ | BSD-3-Clause | Compose target |
| redis-py | https://github.com/redis/redis-py | MIT | Installed for Celery/Valkey protocol compatibility |
| django-axes | https://github.com/jazzband/django-axes | MIT | Installed |
| django-otp | https://github.com/django-otp/django-otp | Unlicense | Installed |
| django-htmx | https://github.com/adamchainz/django-htmx | MIT | Installed |
| pytest and pytest-django | https://pytest.org/ | MIT/BSD | Installed |
| Ruff | https://docs.astral.sh/ruff/ | MIT | Installed |
| mypy | https://mypy-lang.org/ | MIT | Installed |
| Playwright | https://playwright.dev/ | Apache-2.0 | Installed |
| Tailwind CSS | https://tailwindcss.com/ | MIT | Installed |
| FreeRADIUS | https://www.freeradius.org/ | GPL project; integration/schema implications require review | Candidate only |
| MikroTik RouterOS documentation | https://help.mikrotik.com/docs/ | Proprietary product documentation | Reference only |
| Safaricom Daraja documentation | https://developer.safaricom.co.ke/ | Proprietary API documentation | Reference only |
| Caddy | https://caddyserver.com/ | Apache-2.0 | Optional Compose profile |

## Attribution Requirements

Generated report: `docs/reuse/phase-1-licence-report.md`.
