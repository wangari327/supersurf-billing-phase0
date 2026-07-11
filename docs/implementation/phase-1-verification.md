# Phase 1 Verification Results

Date: 2026-07-11

## Commits

- Phase 0.5: `c5016c1` - Correct Phase 0 domain and security design
- Phase 1: this commit - Add lean Phase 1 Django foundation

## Local Tooling

- Python: 3.13.5
- uv: 0.11.28, installed as a temporary workspace-local tool for this run
- Node.js: 22.16.0
- npm: 10.9.2
- Docker client: 27.2.1
- Docker Compose: not available on PATH
- Docker daemon: not reachable from this session

## Checks Run

| Check | Result |
| --- | --- |
| `uv lock` | Passed |
| `uv sync` | Passed |
| `npm install --include=optional` | Passed |
| `npm run build:css` | Passed |
| `python manage.py migrate` | Passed on empty local SQLite database |
| `python manage.py seed_roles` | Passed |
| `pytest -q` | Passed, 19 tests |
| `ruff check .` | Passed |
| `mypy supersurf core users audit` | Passed |
| `python manage.py check` | Passed |
| `python manage.py check --deploy --fail-level WARNING` with production check env | Passed |
| `pip-audit` | Passed, no known vulnerabilities found |
| `pip-licenses --format=markdown --with-system` | Passed; report written to `docs/reuse/phase-1-licence-report.md` |
| `python scripts/scan_secrets.py` | Passed |
| `npm audit --audit-level=moderate` | Passed |
| `python manage.py collectstatic --noinput` | Passed |

## Docker And Valkey

`compose.yaml` defines:

- `web`
- `worker`
- `scheduler`
- `postgres`
- `broker`

`compose.caddy.yaml` defines optional `caddy` profile.

Docker Compose validation could not be run because neither `docker compose` nor `docker-compose` is installed in this environment.

The Valkey runtime compatibility check could not be completed because the Docker daemon was not reachable. Dependency resolution confirms Celery/Kombu 5.6.3 is compatible with redis-py 6.4.0, and Compose targets `valkey/valkey:8-alpine`.

## Playwright

The bundled Playwright Chromium download timed out locally. The Playwright smoke test passed using the installed local Chrome fallback. CI installs Playwright Chromium explicitly.

## Phase Boundary

Phase 2 has not begun. The repository contains no M-PESA implementation, subscriber billing, wallets, ledger transactions, FreeRADIUS provisioning, PPPoE implementation, RouterOS integration, or live network actions.
