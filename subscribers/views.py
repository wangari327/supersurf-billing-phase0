from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from billing.models import Plan, Subscription

from .forms import ServiceForm, SubscriberForm, SubscriberSearchForm
from .models import Service, Subscriber
from .services import (
    create_service,
    create_subscriber,
    set_service_active,
    set_subscriber_active,
    update_service,
    update_subscriber,
)

SERVICE_REFERENCE_RE = re.compile(r"^SS\d{6}-\d{2}$", re.IGNORECASE)


def _query_string_without_page(query_params) -> str:
    query_params = query_params.copy()
    query_params.pop("page", None)
    return query_params.urlencode()


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
def subscriber_list(request):
    can_view_services = request.user.has_perm("subscribers.view_service")
    form_data = request.GET.copy()
    form = SubscriberSearchForm(form_data, can_view_services=can_view_services)
    subscribers = Subscriber.objects.all()
    if can_view_services:
        subscribers = subscribers.annotate(service_count=Count("services", distinct=True))
    query = ""
    status = ""
    safe_query_params = request.GET.copy()
    if form.is_valid():
        query = form.cleaned_data["q"].strip()
        status = form.cleaned_data["status"]
        hidden_service_reference_query = (
            bool(query) and not can_view_services and SERVICE_REFERENCE_RE.fullmatch(query)
        )
        if hidden_service_reference_query:
            subscribers = subscribers.none()
            query = ""
            form_data["q"] = ""
            safe_query_params.pop("q", None)
            form = SubscriberSearchForm(form_data, can_view_services=can_view_services)
        elif query:
            search_filter = (
                Q(account_number__icontains=query)
                | Q(display_name__icontains=query)
                | Q(primary_phone__icontains=query)
            )
            if can_view_services:
                search_filter |= Q(services__service_reference__icontains=query)
            subscribers = subscribers.filter(search_filter).distinct()
        if status == "active":
            subscribers = subscribers.filter(is_active=True)
        elif status == "inactive":
            subscribers = subscribers.filter(is_active=False)
    paginator = Paginator(subscribers.order_by("account_number"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "subscribers/subscriber_list.html",
        {
            "form": form,
            "page": page,
            "query": query,
            "status": status,
            "query_string": _query_string_without_page(safe_query_params),
            "can_view_services": can_view_services,
        },
    )


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
def subscriber_detail(request, pk):
    can_view_services = request.user.has_perm("subscribers.view_service")
    can_view_subscriptions = can_view_services and request.user.has_perm(
        "billing.view_subscription"
    )
    can_add_service = request.user.has_perm("subscribers.add_service")
    can_change_service = request.user.has_perm("subscribers.change_service")
    can_assign_subscription = can_view_services and request.user.has_perm(
        "billing.add_subscription"
    )
    can_change_subscription = can_view_services and request.user.has_perm(
        "billing.change_subscription"
    )
    subscribers = Subscriber.objects.all()
    if can_view_services:
        subscribers = subscribers.prefetch_related("services")
    subscriber = get_object_or_404(subscribers, pk=pk)
    service_rows = []
    active_plans = []
    if can_view_services:
        if can_assign_subscription or can_change_subscription:
            active_plans = list(
                Plan.objects.filter(is_active=True).order_by(
                    "download_speed_mbps",
                    "price_minor",
                    "name",
                )
            )
        for service in subscriber.services.all():
            history = []
            current_subscription = None
            if can_view_subscriptions:
                history = list(
                    service.subscriptions.select_related("plan").order_by("-created_at", "-id")
                )
                current_subscription = next(
                    (
                        subscription
                        for subscription in history
                        if subscription.status == Subscription.STATUS_ACTIVE
                    ),
                    None,
                )
            service_rows.append(
                {
                    "service": service,
                    "history": history,
                    "current_subscription": current_subscription,
                }
            )
    return render(
        request,
        "subscribers/subscriber_detail.html",
        {
            "subscriber": subscriber,
            "can_view_services": can_view_services,
            "can_view_subscriptions": can_view_subscriptions,
            "can_add_service": can_add_service,
            "can_change_service": can_change_service,
            "can_assign_subscription": can_assign_subscription,
            "can_change_subscription": can_change_subscription,
            "service_rows": service_rows,
            "service_count": len(service_rows),
            "active_plans": active_plans,
        },
    )


@login_required
@permission_required("subscribers.add_subscriber", raise_exception=True)
def subscriber_create(request):
    if request.method == "POST":
        form = SubscriberForm(request.POST)
        if form.is_valid():
            subscriber = create_subscriber(form=form, actor=request.user, request=request)
            messages.success(request, f"Subscriber {subscriber.account_number} created.")
            return redirect("subscriber_detail", pk=subscriber.pk)
    else:
        form = SubscriberForm(initial={"customer_type": Subscriber.CUSTOMER_INDIVIDUAL})
    return render(
        request,
        "subscribers/subscriber_form.html",
        {"form": form, "title": "Create Subscriber", "submit_label": "Create subscriber"},
    )


@login_required
@permission_required("subscribers.change_subscriber", raise_exception=True)
def subscriber_edit(request, pk):
    subscriber = get_object_or_404(Subscriber, pk=pk)
    if request.method == "POST":
        form = SubscriberForm(request.POST, instance=subscriber)
        if form.is_valid():
            subscriber = update_subscriber(
                subscriber=subscriber,
                form=form,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Subscriber {subscriber.account_number} updated.")
            return redirect("subscriber_detail", pk=subscriber.pk)
    else:
        form = SubscriberForm(instance=subscriber)
    return render(
        request,
        "subscribers/subscriber_form.html",
        {
            "form": form,
            "subscriber": subscriber,
            "title": "Edit Subscriber",
            "submit_label": "Save subscriber",
        },
    )


@login_required
@permission_required("subscribers.change_subscriber", raise_exception=True)
def subscriber_deactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    subscriber = get_object_or_404(Subscriber, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to deactivate a subscriber.")
        return redirect("subscriber_detail", pk=subscriber.pk)
    try:
        subscriber = set_subscriber_active(
            subscriber=subscriber,
            is_active=False,
            reason=reason,
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(
            request,
            f"Subscriber {subscriber.account_number} deactivated. Services remain unchanged.",
        )
    return redirect("subscriber_detail", pk=subscriber.pk)


@login_required
@permission_required("subscribers.change_subscriber", raise_exception=True)
def subscriber_reactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    subscriber = get_object_or_404(Subscriber, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to reactivate a subscriber.")
        return redirect("subscriber_detail", pk=subscriber.pk)
    try:
        subscriber = set_subscriber_active(
            subscriber=subscriber,
            is_active=True,
            reason=reason,
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"Subscriber {subscriber.account_number} reactivated.")
    return redirect("subscriber_detail", pk=subscriber.pk)


@login_required
@permission_required("subscribers.add_service", raise_exception=True)
def service_create(request, subscriber_pk):
    subscriber = get_object_or_404(Subscriber, pk=subscriber_pk)
    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            try:
                service = create_service(
                    subscriber=subscriber,
                    form=form,
                    actor=request.user,
                    request=request,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, f"Service {service.service_reference} created.")
                return redirect("subscriber_detail", pk=subscriber.pk)
    else:
        form = ServiceForm()
    return render(
        request,
        "subscribers/service_form.html",
        {
            "form": form,
            "subscriber": subscriber,
            "title": "Create Service",
            "submit_label": "Create service",
        },
    )


@login_required
@permission_required("subscribers.change_service", raise_exception=True)
def service_edit(request, pk):
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=pk)
    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            service = update_service(
                service=service,
                form=form,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Service {service.service_reference} updated.")
            return redirect("subscriber_detail", pk=service.subscriber_id)
    else:
        form = ServiceForm(instance=service)
    return render(
        request,
        "subscribers/service_form.html",
        {
            "form": form,
            "service": service,
            "subscriber": service.subscriber,
            "title": "Edit Service",
            "submit_label": "Save service",
        },
    )


@login_required
@permission_required("subscribers.change_service", raise_exception=True)
def service_deactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to deactivate a service.")
        return redirect("subscriber_detail", pk=service.subscriber_id)
    try:
        service = set_service_active(
            service=service,
            is_active=False,
            reason=reason,
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"Service {service.service_reference} deactivated.")
    return redirect("subscriber_detail", pk=service.subscriber_id)


@login_required
@permission_required("subscribers.change_service", raise_exception=True)
def service_reactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to reactivate a service.")
        return redirect("subscriber_detail", pk=service.subscriber_id)
    try:
        service = set_service_active(
            service=service,
            is_active=True,
            reason=reason,
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"Service {service.service_reference} reactivated.")
    return redirect("subscriber_detail", pk=service.subscriber_id)
