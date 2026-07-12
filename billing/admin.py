from __future__ import annotations

from django.contrib import admin

from .models import BillingPeriod, Plan, Subscription


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


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "plan_name",
        "status",
        "starts_at",
        "ended_at",
        "price_minor",
    )
    list_filter = ("status", "currency")
    search_fields = ("service__service_reference", "plan_name")
    readonly_fields = [field.name for field in Subscription._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "sequence_number",
        "period_type",
        "plan_name",
        "starts_at",
        "expires_at",
        "grace_until",
        "price_minor",
    )
    list_filter = ("period_type", "currency")
    search_fields = ("service__service_reference", "plan_name")
    readonly_fields = [field.name for field in BillingPeriod._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions
