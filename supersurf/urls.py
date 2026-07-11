from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from audit.views import audit_log
from core import views as core_views
from users import views as user_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", core_views.dashboard, name="dashboard"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password-change/",
        user_views.audited_password_change,
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path("settings/", core_views.organization_settings, name="organization_settings"),
    path("healthz/", core_views.healthz, name="healthz"),
    path("readyz/", core_views.readyz, name="readyz"),
    path("system/health/", core_views.system_health, name="system_health"),
    path("staff/", user_views.staff_list, name="staff_list"),
    path("staff/<int:pk>/", user_views.staff_detail, name="staff_detail"),
    path("staff/<int:pk>/roles/", user_views.assign_roles, name="assign_roles"),
    path("audit/", audit_log, name="audit_log"),
    path("", include("billing.urls")),
]
