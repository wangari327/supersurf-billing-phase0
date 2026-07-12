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
    path(
        "services/<uuid:service_pk>/subscriptions/assign/",
        views.subscription_assign,
        name="subscription_assign",
    ),
    path(
        "subscriptions/<uuid:pk>/change-package/",
        views.subscription_change_package,
        name="subscription_change_package",
    ),
    path("subscriptions/<uuid:pk>/end/", views.subscription_end, name="subscription_end"),
    path(
        "services/<uuid:service_pk>/billing-periods/activate/",
        views.billing_period_activate,
        name="billing_period_activate",
    ),
    path(
        "services/<uuid:service_pk>/billing-periods/renew/",
        views.billing_period_renew,
        name="billing_period_renew",
    ),
    path(
        "services/<uuid:service_pk>/billing-periods/",
        views.billing_period_history,
        name="billing_period_history",
    ),
    path(
        "subscribers/<uuid:subscriber_pk>/wallet/",
        views.wallet_detail,
        name="wallet_detail",
    ),
    path(
        "subscribers/<uuid:subscriber_pk>/wallet/adjustments/",
        views.wallet_adjustment,
        name="wallet_adjustment",
    ),
    path(
        "ledger-entries/<uuid:entry_pk>/reverse/",
        views.ledger_entry_reverse,
        name="ledger_entry_reverse",
    ),
]
