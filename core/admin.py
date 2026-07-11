from __future__ import annotations

from django.contrib import admin

from .models import Organization, OrganizationBranding


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("trading_name", "product_name", "country_code", "currency")
    readonly_fields = [field.name for field in Organization._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(OrganizationBranding)
class OrganizationBrandingAdmin(admin.ModelAdmin):
    list_display = ("organization", "receipt_heading", "invoice_heading")
    readonly_fields = [field.name for field in OrganizationBranding._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
