from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("subscribers/", views.subscriber_list, name="subscriber_list"),
    path("subscribers/new/", views.subscriber_create, name="subscriber_create"),
    path("subscribers/<uuid:pk>/", views.subscriber_detail, name="subscriber_detail"),
    path("subscribers/<uuid:pk>/edit/", views.subscriber_edit, name="subscriber_edit"),
    path(
        "subscribers/<uuid:pk>/deactivate/",
        views.subscriber_deactivate,
        name="subscriber_deactivate",
    ),
    path(
        "subscribers/<uuid:pk>/reactivate/",
        views.subscriber_reactivate,
        name="subscriber_reactivate",
    ),
    path(
        "subscribers/<uuid:subscriber_pk>/services/new/",
        views.service_create,
        name="service_create",
    ),
    path("services/<uuid:pk>/edit/", views.service_edit, name="service_edit"),
    path("services/<uuid:pk>/deactivate/", views.service_deactivate, name="service_deactivate"),
    path("services/<uuid:pk>/reactivate/", views.service_reactivate, name="service_reactivate"),
]
