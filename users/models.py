from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField(max_length=160, blank=True)

    class Meta:
        permissions = [
            ("assign_roles", "Can assign staff roles"),
            ("view_staff_security", "Can view staff security details"),
        ]

    def __str__(self) -> str:
        return self.display_name or self.get_username()

    @property
    def role_names(self) -> list[str]:
        return list(self.groups.order_by("name").values_list("name", flat=True))

