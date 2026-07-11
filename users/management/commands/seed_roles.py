from __future__ import annotations

from django.core.management.base import BaseCommand

from users.services import seed_roles_and_permissions


class Command(BaseCommand):
    help = "Seed SuperSurf staff roles and permissions."

    def handle(self, *args, **options) -> None:
        seed_roles_and_permissions()
        self.stdout.write(self.style.SUCCESS("Seeded SuperSurf roles and permissions."))

