# Local Setup

## Requirements

- Python 3.13
- uv
- Node.js 22 or compatible current LTS
- npm
- Docker with Compose plugin for PostgreSQL and Valkey workflows

This machine used Python 3.13.5 and a temporary workspace-local uv 0.11.28 tool because `uv` was not installed globally.

## Install

```powershell
uv sync
npm ci --include=optional
npm run build:css
```

## Database

For quick local development without Docker, Django falls back to SQLite:

```powershell
uv run python manage.py migrate
uv run python manage.py seed_roles
```

For PostgreSQL development, use `compose.yaml` when Docker Compose is available:

```powershell
docker compose up --build
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py seed_roles
```

This Compose stack is development-only. It uses Django `runserver`, development credentials, PostgreSQL, and Valkey for local workflows. The optional Caddy file is a local reverse-proxy preview:

```powershell
docker compose -f compose.yaml -f compose.caddy.yaml --profile local-tls-preview up --build
```

Do not treat Django `runserver` plus Caddy as a production WSGI deployment.

## First Owner

Create the first owner explicitly:

```powershell
$env:FIRST_OWNER_PASSWORD="replace-with-a-local-secret"
uv run python manage.py create_first_owner --username owner --email ""
Remove-Item Env:FIRST_OWNER_PASSWORD
```

Do not commit real passwords or production credentials.
