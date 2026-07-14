from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Show sandbox Daraja callback URLs for an authenticated operator session."

    def handle(self, *args, **options) -> None:
        token = settings.MPESA_CALLBACK_TOKEN.strip()
        if len(token) < 32:
            raise CommandError(
                "MPESA_CALLBACK_TOKEN must be configured and at least 32 characters."
            )
        base_url = settings.MPESA_CALLBACK_BASE_URL.rstrip("/")
        self.stdout.write(
            "C2B Validation URL: "
            f"{base_url}/api/integrations/mpesa/{token}/c2b/validation/"
        )
        self.stdout.write(
            "C2B Confirmation URL: "
            f"{base_url}/api/integrations/mpesa/{token}/c2b/confirmation/"
        )
        self.stdout.write(
            f"STK Callback URL: {base_url}/api/integrations/mpesa/{token}/stk/callback/"
        )
