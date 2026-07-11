from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.services import get_or_create_default_organization, production_readiness_issues


class Command(BaseCommand):
    help = "Check whether required production settings are present."

    def handle(self, *args, **options) -> None:
        organization = get_or_create_default_organization()
        issues = production_readiness_issues(organization)
        for issue in issues:
            self.stdout.write(f"{issue.severity}: {issue.code}: {issue.message}")
        if any(issue.severity == "error" for issue in issues):
            raise CommandError("Production readiness checks failed.")
        self.stdout.write("production readiness check complete")

