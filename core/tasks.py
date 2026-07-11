from __future__ import annotations

from supersurf.celery import app


@app.task(name="core.health_check")
def health_check() -> str:
    return "ok"

