from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SuperSurfUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("SuperSurf", {"fields": ("display_name",)}),)
    list_display = ("username", "email", "display_name", "is_staff", "is_active")

