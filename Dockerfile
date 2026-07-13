FROM node:22-bookworm-slim AS css-builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --include=optional

COPY . .
RUN npm run build:css


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN addgroup --system supersurf && adduser --system --ingroup supersurf supersurf

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.11.28 \
    && uv sync --frozen --no-dev

COPY . .
COPY --from=css-builder /app/static/css/app.css ./static/css/app.css

RUN SUPERSURF_STATICFILES_MANIFEST=true uv run --no-dev python manage.py collectstatic --noinput \
    && chown -R supersurf:supersurf /app

USER supersurf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["uv", "run", "--no-dev", "python", "manage.py", "healthcheck"]

CMD ["uv", "run", "--no-dev", "gunicorn", "supersurf.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "60", "--error-logfile", "-", "--capture-output"]
