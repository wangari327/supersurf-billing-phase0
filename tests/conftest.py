from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from users.models import User


@pytest.fixture
def seeded_roles(db):
    call_command("seed_roles", verbosity=0)


@pytest.fixture
def owner_user(seeded_roles):
    user = User.objects.create_user(username="owner", password="StrongOwnerPass123!", is_staff=True)
    user.groups.add(Group.objects.get(name="Owner"))
    return user


@pytest.fixture
def readonly_user(seeded_roles):
    user = User.objects.create_user(username="readonly", password="StrongReadOnlyPass123!")
    user.groups.add(Group.objects.get(name="Read Only"))
    return user

