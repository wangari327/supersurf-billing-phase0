from __future__ import annotations

import getpass
import os

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from users.services import create_owner_user


class Command(BaseCommand):
    help = "Create the first Owner account without storing a default password."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--password-env",
            default="FIRST_OWNER_PASSWORD",
            help="Environment variable containing the initial password.",
        )

    def handle(self, *args, **options) -> None:
        call_command("seed_roles", verbosity=0)
        password = os.environ.get(options["password_env"])
        if not password:
            password = getpass.getpass("Initial owner password: ")
        if not password:
            raise CommandError("Owner password was not supplied.")
        try:
            user = create_owner_user(
                username=options["username"],
                email=options["email"],
                password=password,
            )
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS(f"Created Owner user {user.username}."))
