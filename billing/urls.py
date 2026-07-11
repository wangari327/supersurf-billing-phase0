from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("packages/", views.package_list, name="package_list"),
    path("packages/new/", views.package_create, name="package_create"),
    path("packages/<uuid:pk>/", views.package_detail, name="package_detail"),
    path("packages/<uuid:pk>/edit/", views.package_edit, name="package_edit"),
    path("packages/<uuid:pk>/deactivate/", views.package_deactivate, name="package_deactivate"),
    path("packages/<uuid:pk>/reactivate/", views.package_reactivate, name="package_reactivate"),
]
