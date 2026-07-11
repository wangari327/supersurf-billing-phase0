from __future__ import annotations

from django.db import models


class Organization(models.Model):
    primary_brand = models.CharField(max_length=120, default="SuperSurf")
    trading_name = models.CharField(max_length=120, default="SuperSurf")
    product_name = models.CharField(max_length=120, default="SuperSurf Billing")
    network_label = models.CharField(max_length=120, default="SuperSurf Networks")
    support_label = models.CharField(max_length=120, default="SuperSurf Support")
    portal_label = models.CharField(max_length=120, default="SuperSurf Portal")

    registered_business_name = models.CharField(max_length=180, blank=True)
    domain = models.CharField(max_length=180, blank=True)
    support_email = models.EmailField(blank=True)
    billing_email = models.EmailField(blank=True)
    noc_email = models.EmailField("NOC email", blank=True)
    support_phone = models.CharField(max_length=40, blank=True)
    paybill_number = models.CharField(max_length=40, blank=True)
    till_number = models.CharField(max_length=40, blank=True)
    kra_pin = models.CharField("KRA PIN", max_length=40, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    communications_authority_licence = models.CharField(max_length=180, blank=True)

    country = models.CharField(max_length=80, default="Kenya")
    country_code = models.CharField(max_length=2, default="KE")
    currency = models.CharField(max_length=3, default="KES")
    currency_display_label = models.CharField(max_length=12, default="KSh")
    timezone = models.CharField(max_length=80, default="Africa/Nairobi")
    locale = models.CharField(max_length=20, default="en-KE")
    date_format = models.CharField(max_length=20, default="DD/MM/YYYY")
    time_format = models.CharField(max_length=20, default="24-hour")
    week_start = models.CharField(max_length=20, default="Monday")
    telephone_country_code = models.CharField(max_length=8, default="+254")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("view_sensitive_settings", "Can view sensitive settings"),
            ("change_sensitive_settings", "Can change sensitive settings"),
            ("run_production_readiness_checks", "Can run production readiness checks"),
        ]

    def __str__(self) -> str:
        return self.trading_name


class OrganizationBranding(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="branding"
    )
    logo = models.FileField(upload_to="branding/", blank=True)
    favicon = models.FileField(upload_to="branding/", blank=True)
    primary_ui_colour = models.CharField(max_length=20, default="#075985")
    secondary_ui_colour = models.CharField(max_length=20, default="#15803d")
    receipt_heading = models.CharField(max_length=160, default="SuperSurf Billing")
    invoice_heading = models.CharField(max_length=160, default="SuperSurf Billing")
    receipt_footer = models.TextField(blank=True)
    invoice_footer = models.TextField(blank=True)
    payment_instructions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.organization.trading_name} branding"
