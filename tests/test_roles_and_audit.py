from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse

from audit.models import AuditEvent
from audit.service import record_event, safe_metadata
from users.services import invalidate_user_sessions


@pytest.mark.django_db
def test_group_and_permission_seeding(seeded_roles):
    owner = Group.objects.get(name="Owner")
    readonly = Group.objects.get(name="Read Only")
    assert owner.permissions.filter(codename="assign_roles").exists()
    assert readonly.permissions.filter(codename="view_user").exists()


@pytest.mark.django_db
def test_unauthorized_settings_access(client, readonly_user):
    client.force_login(readonly_user)
    response = client.get(reverse("organization_settings"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_role_change_authorization(client, owner_user, readonly_user):
    client.force_login(readonly_user)
    response = client.get(reverse("assign_roles", args=[readonly_user.pk]))
    assert response.status_code == 403

    client.force_login(owner_user)
    response = client.post(
        reverse("assign_roles", args=[readonly_user.pk]),
        {"roles": [Group.objects.get(name="Finance").pk], "reason": "Finance handover"},
    )
    assert response.status_code == 302
    readonly_user.refresh_from_db()
    assert list(readonly_user.groups.values_list("name", flat=True)) == ["Finance"]
    assert AuditEvent.objects.filter(action="staff.roles.changed").exists()


@pytest.mark.django_db
def test_audit_event_creation(owner_user):
    event = record_event(
        action="test.action",
        actor=owner_user,
        target_type="unit",
        target_identifier="123",
        metadata={"token": "secret-token", "safe": "value"},
    )
    assert event.safe_metadata["token"] == "[redacted]"
    assert event.safe_metadata["safe"] == "value"


@pytest.mark.django_db
def test_audit_event_is_append_only(owner_user):
    event = record_event(action="test.append_only", actor=owner_user)
    event.action = "changed"
    with pytest.raises(RuntimeError):
        event.save()
    with pytest.raises(RuntimeError):
        event.delete()


def test_audit_redaction_helper():
    metadata = safe_metadata({"consumer_secret": "abc", "nested": {"password": "def"}})
    assert metadata["consumer_secret"] == "[redacted]"
    assert metadata["nested"]["password"] == "[redacted]"


@pytest.mark.django_db
def test_session_invalidation(owner_user):
    session = SessionStore()
    session["_auth_user_id"] = str(owner_user.pk)
    session.save()
    removed = invalidate_user_sessions(owner_user.pk)
    assert removed == 1
