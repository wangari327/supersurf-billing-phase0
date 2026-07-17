from __future__ import annotations

from django.contrib import admin

from .models import (
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    MpesaCallbackEvent,
    MpesaCallbackPaymentLink,
    Payment,
    PaymentAllocation,
    PaymentProviderProfile,
    Plan,
    Subscription,
    UnmatchedPaymentCase,
    Wallet,
)


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


@admin.register(BillingCharge)
class BillingChargeAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "charge_type",
        "amount_minor",
        "currency",
        "billing_period",
        "ledger_entry",
        "created_by",
        "created_at",
    )
    list_filter = ("charge_type", "currency")
    search_fields = ("service__service_reference", "reason")
    readonly_fields = [field.name for field in BillingCharge._meta.fields]

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


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "currency", "created_at")
    list_filter = ("currency",)
    search_fields = ("subscriber__account_number",)
    readonly_fields = [field.name for field in Wallet._meta.fields]

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


@admin.register(PaymentProviderProfile)
class PaymentProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider",
        "product_type",
        "environment",
        "external_identifier",
        "is_active",
    )
    list_filter = ("provider", "product_type", "environment", "is_active")
    search_fields = ("name", "external_identifier")
    readonly_fields = [field.name for field in PaymentProviderProfile._meta.fields]

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


@admin.register(MpesaCallbackEvent)
class MpesaCallbackEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "provider_transaction_id",
        "checkout_request_id",
        "account_reference",
        "result_code",
        "received_at",
    )
    list_filter = ("event_type", "result_code")
    search_fields = (
        "provider_transaction_id",
        "checkout_request_id",
        "merchant_request_id",
        "account_reference",
        "payload_sha256",
    )
    readonly_fields = [field.name for field in MpesaCallbackEvent._meta.fields]

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


@admin.register(MpesaCallbackPaymentLink)
class MpesaCallbackPaymentLinkAdmin(admin.ModelAdmin):
    list_display = ("callback_event", "payment", "created_at")
    search_fields = ("callback_event__id", "payment__id")
    readonly_fields = [field.name for field in MpesaCallbackPaymentLink._meta.fields]

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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "provider_transaction_id",
        "provider_profile",
        "amount_minor",
        "currency",
        "account_reference",
        "received_at",
    )
    list_filter = ("currency", "provider_profile__provider", "provider_profile__environment")
    search_fields = (
        "provider_transaction_id",
        "account_reference",
        "provider_profile__name",
    )
    readonly_fields = [field.name for field in Payment._meta.fields]

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


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "wallet",
        "amount_minor",
        "currency",
        "ledger_entry",
        "created_by",
        "created_at",
    )
    list_filter = ("currency", "allocation_type")
    search_fields = (
        "payment__provider_transaction_id",
        "wallet__subscriber__account_number",
    )
    readonly_fields = [field.name for field in PaymentAllocation._meta.fields]

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


@admin.register(UnmatchedPaymentCase)
class UnmatchedPaymentCaseAdmin(admin.ModelAdmin):
    list_display = ("payment", "status", "reason_code", "opened_at", "resolved_at")
    list_filter = ("status", "reason_code")
    search_fields = ("payment__provider_transaction_id", "payment__account_reference")
    readonly_fields = [field.name for field in UnmatchedPaymentCase._meta.fields]

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


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "wallet",
        "sequence_number",
        "entry_type",
        "direction",
        "amount_minor",
        "balance_after_minor",
        "created_by",
        "created_at",
    )
    list_filter = ("entry_type", "direction", "currency")
    search_fields = ("wallet__subscriber__account_number", "reason")
    readonly_fields = [field.name for field in LedgerEntry._meta.fields]

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
