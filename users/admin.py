from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import User

try:
    admin.site.unregister(Group)
except NotRegistered:
    pass


@admin.register(User)
class SuperSurfUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Safe profile fields", {"fields": ("display_name", "first_name", "last_name", "email")}),
        ("Account status", {"fields": ("is_active", "last_login", "date_joined")}),
    )
    filter_horizontal = ()
    list_display = ("username", "email", "display_name", "is_staff", "is_active")
    readonly_fields = [
        "username",
        "password",
        "display_name",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "last_login",
        "date_joined",
    ]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
