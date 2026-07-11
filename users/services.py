from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from audit.service import record_event

from .roles import ROLE_NAMES, ROLE_OWNER, ROLE_PERMISSION_CODENAMES, is_owner


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
    user = user_model(
        username=username,
        email=email,
        is_staff=True,
        is_superuser=False,
    )
    validate_password(password, user)
    user.set_password(password)
    user.save()
    owner_group = Group.objects.get(name="Owner")
    user.groups.add(owner_group)
    return user


def invalidate_user_sessions(user_id: int, *, exclude_session_key: str | None = None) -> int:
    removed = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if exclude_session_key and session.session_key == exclude_session_key:
            continue
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user_id):
            session.delete()
            removed += 1
    return removed


@dataclass(frozen=True)
class RoleAssignmentResult:
    old_roles: list[str]
    new_roles: list[str]
    removed_sessions: int


def _role_names(groups: Iterable[Group]) -> list[str]:
    return sorted(group.name for group in groups)


def _validate_role_authorization(
    *,
    actor,
    target_user,
    old_roles: set[str],
    new_roles: set[str],
) -> None:
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Role changes require an authenticated staff user.")
    if not actor.has_perm("users.assign_roles"):
        raise PermissionDenied("You do not have permission to assign roles.")

    actor_is_owner = is_owner(actor)
    target_is_owner = ROLE_OWNER in old_roles
    owner_role_changed = (ROLE_OWNER in old_roles) != (ROLE_OWNER in new_roles)
    owner_role_granted = ROLE_OWNER in new_roles and ROLE_OWNER not in old_roles

    if target_is_owner and not actor_is_owner:
        raise PermissionDenied("Only an Owner may modify another Owner's roles.")
    if (owner_role_changed or owner_role_granted) and not actor_is_owner:
        raise PermissionDenied("Only an Owner may grant or remove the Owner role.")

    if target_user.is_active and ROLE_OWNER in old_roles and ROLE_OWNER not in new_roles:
        remaining_active_owners = (
            get_user_model()
            .objects.select_for_update()
            .filter(is_active=True, groups__name=ROLE_OWNER)
            .exclude(pk=target_user.pk)
            .distinct()
            .count()
        )
        if remaining_active_owners == 0:
            raise ValidationError("Cannot remove the final active Owner role.")


@transaction.atomic
def assign_roles_to_user(
    *,
    actor,
    target_user,
    roles: Iterable[Group],
    reason: str,
    request: HttpRequest | None = None,
    current_session_key: str | None = None,
) -> RoleAssignmentResult:
    user_model = get_user_model()
    locked_target = user_model.objects.select_for_update().get(pk=target_user.pk)
    requested_group_ids = [group.pk for group in roles]
    requested_groups = list(
        Group.objects.select_for_update()
        .filter(pk__in=requested_group_ids, name__in=ROLE_NAMES)
        .order_by("name")
    )
    if len(requested_groups) != len(set(requested_group_ids)):
        raise ValidationError("One or more requested roles are not valid SuperSurf roles.")

    old_role_names = set(locked_target.groups.values_list("name", flat=True))
    new_role_names = set(_role_names(requested_groups))
    _validate_role_authorization(
        actor=actor,
        target_user=locked_target,
        old_roles=old_role_names,
        new_roles=new_role_names,
    )

    old_roles = sorted(old_role_names)
    locked_target.groups.set(requested_groups)
    new_roles = sorted(new_role_names)
    removed_sessions = invalidate_user_sessions(
        locked_target.pk,
        exclude_session_key=current_session_key,
    )
    record_event(
        action="staff.roles.changed",
        actor=actor,
        request=request,
        target_type="user",
        target_identifier=locked_target.pk,
        metadata={
            "old_roles": old_roles,
            "new_roles": new_roles,
            "removed_sessions": removed_sessions,
        },
        reason=reason,
    )
    return RoleAssignmentResult(
        old_roles=old_roles,
        new_roles=new_roles,
        removed_sessions=removed_sessions,
    )
