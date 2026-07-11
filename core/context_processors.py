from __future__ import annotations

from django.conf import settings

from .services import environment_badge_colour


def environment_banner(_request):
    return {
        "SUPERSURF_ENVIRONMENT": settings.SUPERSURF_ENVIRONMENT,
        "SUPERSURF_ENVIRONMENT_CLASSES": environment_badge_colour(),
    }

