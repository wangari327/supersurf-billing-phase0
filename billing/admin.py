from __future__ import annotations

from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "download_speed_mbps", "price_minor", "currency", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("name",)
    readonly_fields = [field.name for field in Plan._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
