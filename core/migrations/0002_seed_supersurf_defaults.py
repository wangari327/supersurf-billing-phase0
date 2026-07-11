from __future__ import annotations

from django.db import migrations


def seed_supersurf(apps, schema_editor):
    organization_model = apps.get_model("core", "Organization")
    branding_model = apps.get_model("core", "OrganizationBranding")
    organization, _ = organization_model.objects.get_or_create(
        pk=1,
        defaults={
            "primary_brand": "SuperSurf",
            "trading_name": "SuperSurf",
            "product_name": "SuperSurf Billing",
            "network_label": "SuperSurf Networks",
            "support_label": "SuperSurf Support",
            "portal_label": "SuperSurf Portal",
            "country": "Kenya",
            "country_code": "KE",
            "currency": "KES",
            "currency_display_label": "KSh",
            "timezone": "Africa/Nairobi",
            "locale": "en-KE",
            "date_format": "DD/MM/YYYY",
            "time_format": "24-hour",
            "week_start": "Monday",
            "telephone_country_code": "+254",
        },
    )
    branding_model.objects.get_or_create(
        organization=organization,
        defaults={
            "primary_ui_colour": "#075985",
            "secondary_ui_colour": "#15803d",
            "receipt_heading": "SuperSurf Billing",
            "invoice_heading": "SuperSurf Billing",
        },
    )


def reverse_seed(apps, schema_editor):
    organization_model = apps.get_model("core", "Organization")
    organization_model.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_supersurf, reverse_seed),
    ]

