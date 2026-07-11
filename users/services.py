from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.utils import timezone

from .roles import ROLE_NAMES, ROLE_PERMISSION_CODENAMES


def seed_roles_and_permissions() -> None:
    all_permissions = Permission.objects.select_related("content_type")
    permission_by_key = {
        f"{permission.content_type.app_label}.{permission.codename}": permission
        for permission in all_permissions
    }
    for role_name in ROLE_NAMES:
        group, _ = Group.objects.get_or_create(name=role_name)
        wanted = ROLE_PERMISSION_CODENAMES[role_name]
        if wanted == ["*"]:
            group.permissions.set(all_permissions)
            continue
        group.permissions.set(
            permission_by_key[key] for key in wanted if key in permission_by_key
        )


def create_owner_user(*, username: str, email: str, password: str) -> Any:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_staff=True,
        is_superuser=False,
    )
    owner_group = Group.objects.get(name="Owner")
    user.groups.add(owner_group)
    return user


def invalidate_user_sessions(user_id: int) -> int:
    removed = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user_id):
            session.delete()
            removed += 1
    return removed
