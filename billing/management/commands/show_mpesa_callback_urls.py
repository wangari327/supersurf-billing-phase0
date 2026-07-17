from __future__ import annotations

from urllib.parse import urlsplit

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
        base_url = settings.MPESA_CALLBACK_BASE_URL.strip().rstrip("/")
        parsed_base_url = urlsplit(base_url)
        if (
            parsed_base_url.scheme.lower() != "https"
            or not parsed_base_url.netloc
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
            or parsed_base_url.path not in {"", "/"}
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise CommandError("MPESA_CALLBACK_BASE_URL must be an absolute HTTPS origin.")
        self.stdout.write(
            "C2B Validation URL: "
            f"{base_url}/api/payment-callbacks/{token}/c2b/validation/"
        )
        self.stdout.write(
            "C2B Confirmation URL: "
            f"{base_url}/api/payment-callbacks/{token}/c2b/confirmation/"
        )
        self.stdout.write(
            f"STK Callback URL: {base_url}/api/payment-callbacks/{token}/stk/callback/"
        )
