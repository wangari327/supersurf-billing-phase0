from __future__ import annotations

from django.contrib import admin

from .models import Organization, OrganizationBranding


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("trading_name", "product_name", "country_code", "currency")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrganizationBranding)
class OrganizationBrandingAdmin(admin.ModelAdmin):
    list_display = ("organization", "receipt_heading", "invoice_heading")
    readonly_fields = ("created_at", "updated_at")

