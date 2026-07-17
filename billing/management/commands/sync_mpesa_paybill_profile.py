from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from billing.services import sync_mpesa_paybill_profile


class Command(BaseCommand):
    help = "Synchronize the approved sandbox M-PESA Paybill provider profile."

    def handle(self, *args, **options):
        try:
            profile = sync_mpesa_paybill_profile()
        except ValidationError as exc:
            raise CommandError("Sandbox Paybill profile synchronization failed safely.") from exc
        if profile is None:
            self.stdout.write("Sandbox Paybill profile synchronization skipped.")
            return
        self.stdout.write(self.style.SUCCESS("Sandbox Paybill profile synchronized."))
