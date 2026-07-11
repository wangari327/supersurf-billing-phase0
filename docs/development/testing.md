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
