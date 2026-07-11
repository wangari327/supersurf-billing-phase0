FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system supersurf && adduser --system --ingroup supersurf supersurf

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.11.28 \
    && uv sync --frozen --no-dev

COPY . .

RUN python manage.py collectstatic --noinput

USER supersurf

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "python", "manage.py", "runserver", "0.0.0.0:8000"]
