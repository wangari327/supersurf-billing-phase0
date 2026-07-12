# Testing And Quality Checks

Run the local checks:

```powershell
uv lock --check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate
uv run python manage.py check
uv run pytest
uv run ruff check .
uv run mypy supersurf core users audit billing subscribers
uv run python scripts/scan_secrets.py
uv run pip-audit
npm audit --audit-level=moderate
npm run build:css
```

Verify migrations from both important local states:

```powershell
uv run python manage.py migrate

@'
import tempfile
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "supersurf.settings")

from django.conf import settings
from django.core.management import call_command

tmp = Path(tempfile.mkdtemp()) / "clean.sqlite3"
settings.DATABASES["default"]["NAME"] = tmp

import django

django.setup()
call_command("migrate", verbosity=0)
print(tmp)
'@ | uv run python -

@'
import tempfile
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "supersurf.settings")

from django.conf import settings
from django.core.management import call_command

tmp = Path(tempfile.mkdtemp()) / "phase5.sqlite3"
settings.DATABASES["default"]["NAME"] = tmp

import django

django.setup()
call_command("migrate", "billing", "0004", verbosity=0)
call_command("migrate", verbosity=0)
print(tmp)
'@ | uv run python -
```

Run production-profile Django deployment checks with a check-only secret:

```powershell
$env:SUPERSURF_ENVIRONMENT="PRODUCTION"
$env:DJANGO_DEBUG="false"
$env:DJANGO_SECRET_KEY="prod-check-9a7bc25f-df43-43bb-b84e-1cf3ee701e6b-Xq84rL9mVz27"
$env:DATABASE_URL="postgres://supersurf:supersurf@localhost:5432/supersurf"
$env:DJANGO_ALLOWED_HOSTS="supersurf.localhost"
$env:DJANGO_CSRF_TRUSTED_ORIGINS="https://supersurf.localhost"
uv run python manage.py check --deploy --fail-level WARNING
```

Run security and dependency checks:

```powershell
uv run python scripts/scan_secrets.py
uv run pip-audit
uv run pip-licenses --format=markdown --with-system --output-file docs/reuse/phase-1-licence-report.md
npm audit --audit-level=moderate
```

Playwright:

```powershell
uv run playwright install chromium
uv run pytest tests/test_auth_and_browser.py
```

On the development machine, the Playwright browser download timed out, so the smoke test uses local Chrome as a fallback. CI installs Chromium explicitly.

## PostgreSQL Concurrency Checks

Local development may use SQLite when `DATABASE_URL` is absent. SQLite is fast for ordinary model, form, permission, and view tests, but it does not prove PostgreSQL row-lock ordering or blocking behavior.

GitHub Actions runs PostgreSQL 17 with empty test-only credentials and sets `DATABASE_URL` for clean migrations, Django checks, deployment checks, and the full pytest suite. Treat the PostgreSQL CI run as authoritative for subscription locking, billing-period concurrency, and wallet-ledger concurrency behavior.

To run the same profile locally, start PostgreSQL and set a test database URL before invoking Django commands:

```powershell
$env:DATABASE_URL="postgres://supersurf_test@localhost:5432/supersurf_test"
uv run python manage.py migrate
uv run python manage.py check
uv run pytest
```
