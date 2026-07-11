from __future__ import annotations

from django.contrib import admin

from .models import Service, Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("account_number", "display_name", "customer_type", "is_active")
    list_filter = ("customer_type", "is_active")
    search_fields = ("account_number", "display_name", "primary_phone")
    readonly_fields = [field.name for field in Subscriber._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_reference", "subscriber", "label", "is_active")
    list_filter = ("is_active",)
    search_fields = ("service_reference", "subscriber__account_number", "label")
    readonly_fields = [field.name for field in Service._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
