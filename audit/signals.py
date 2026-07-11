from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .service import record_event


@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs) -> None:
    record_event(
        action="login.success",
        actor=user,
        request=request,
        target_type="user",
        target_identifier=user.pk,
    )


@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs) -> None:
    record_event(
        action="logout",
        actor=user,
        request=request,
        target_type="user",
        target_identifier=user.pk if user else "",
    )


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs) -> None:
    username = credentials.get("username", "") if credentials else ""
    record_event(
        action="login.failed",
        request=request,
        target_type="user",
        target_identifier=username[:120],
        result="failure",
    )
