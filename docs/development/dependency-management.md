# Dependency Management

Phase 1 uses uv for Python dependency management and npm for the Tailwind CSS build.

## Python

- `pyproject.toml` declares dependencies.
- `uv.lock` pins exact resolved versions.
- Use `uv sync --frozen` in CI.

Common commands:

```powershell
uv lock
uv sync
uv run python manage.py check
```

If `uv` is not installed globally, install it according to uv's official instructions or use a temporary workspace tool. Do not vendor uv into the repository.

## JavaScript

- `package.json` declares the Tailwind build tooling.
- `package-lock.json` pins exact resolved versions.
- Use `npm ci --include=optional` in CI and clean clones.

The `--include=optional` flag is important on Windows because Tailwind's native CSS dependency uses optional platform packages.

## Phase 1 Dependency Decision

redis-py 8.x was not selected because Celery/Kombu 5.6.3 currently constrains Redis transport dependencies to `<6.5`. Phase 1 uses redis-py 6.4.0 with a Valkey 8 container target.

