from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from subscribers.models import Service

from .forms import BillingPeriodActionForm, PackageSearchForm, PlanForm, SubscriptionPackageForm
from .models import BillingPeriod, Plan, Subscription
from .services import (
    activate_billing_period,
    assign_package,
    billing_state_for_service,
    change_subscription_package,
    create_package,
    end_subscription,
    renew_billing_period,
    set_package_active,
    update_package,
)


@login_required
@permission_required("billing.view_plan", raise_exception=True)
def package_list(request):
    form = PackageSearchForm(request.GET)
    packages = Plan.objects.all()
    query = ""
    status = ""
    if form.is_valid():
        query = form.cleaned_data["q"]
        status = form.cleaned_data["status"]
        if query:
            packages = packages.filter(name__icontains=query)
        if status == "active":
            packages = packages.filter(is_active=True)
        elif status == "inactive":
            packages = packages.filter(is_active=False)
    paginator = Paginator(packages, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "billing/package_list.html",
        {"form": form, "page": page, "query": query, "status": status},
    )


@login_required
@permission_required("billing.view_plan", raise_exception=True)
def package_detail(request, pk):
    package = get_object_or_404(Plan, pk=pk)
    active_subscription_count = None
    if request.user.has_perm("billing.view_subscription"):
        active_subscription_count = Subscription.objects.filter(
            plan=package,
            status=Subscription.STATUS_ACTIVE,
        ).count()
    return render(
        request,
        "billing/package_detail.html",
        {"package": package, "active_subscription_count": active_subscription_count},
    )


@login_required
@permission_required("billing.add_plan", raise_exception=True)
def package_create(request):
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            package = create_package(form=form, actor=request.user, request=request)
            messages.success(request, "Package created.")
            return redirect("package_detail", pk=package.pk)
    else:
        form = PlanForm(initial={"duration_days": 30, "grace_period_hours": 24})
    return render(
        request,
        "billing/package_form.html",
        {"form": form, "title": "Create Package", "submit_label": "Create package"},
    )


@login_required
@permission_required("billing.change_plan", raise_exception=True)
def package_edit(request, pk):
    package = get_object_or_404(Plan, pk=pk)
    if request.method == "POST":
        form = PlanForm(request.POST, instance=package)
        if form.is_valid():
            package = update_package(
                plan=package,
                form=form,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Package updated.")
            return redirect("package_detail", pk=package.pk)
    else:
        form = PlanForm(instance=package)
    return render(
        request,
        "billing/package_form.html",
        {"form": form, "package": package, "title": "Edit Package", "submit_label": "Save package"},
    )


@login_required
@permission_required("billing.change_plan", raise_exception=True)
def package_deactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    package = get_object_or_404(Plan, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to deactivate a package.")
        return redirect("package_detail", pk=package.pk)
    set_package_active(
        plan=package,
        is_active=False,
        reason=reason,
        actor=request.user,
        request=request,
    )
    messages.success(request, "Package deactivated.")
    return redirect("package_detail", pk=package.pk)


@login_required
@permission_required("billing.change_plan", raise_exception=True)
def package_reactivate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    package = get_object_or_404(Plan, pk=pk)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to reactivate a package.")
        return redirect("package_detail", pk=package.pk)
    set_package_active(
        plan=package,
        is_active=True,
        reason=reason,
        actor=request.user,
        request=request,
    )
    messages.success(request, "Package reactivated.")
    return redirect("package_detail", pk=package.pk)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.add_subscription", raise_exception=True)
def subscription_assign(request, service_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=service_pk)
    form = SubscriptionPackageForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("subscriber_detail", pk=service.subscriber_id)
    try:
        assign_package(
            service=service,
            plan=form.cleaned_data["plan"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Package assigned.")
    return redirect("subscriber_detail", pk=service.subscriber_id)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.change_subscription", raise_exception=True)
def subscription_change_package(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    subscription = get_object_or_404(
        Subscription.objects.select_related("service", "service__subscriber"),
        pk=pk,
    )
    form = SubscriptionPackageForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("subscriber_detail", pk=subscription.service.subscriber_id)
    try:
        change_subscription_package(
            subscription=subscription,
            plan=form.cleaned_data["plan"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Package changed.")
    return redirect("subscriber_detail", pk=subscription.service.subscriber_id)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.change_subscription", raise_exception=True)
def subscription_end(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    subscription = get_object_or_404(
        Subscription.objects.select_related("service", "service__subscriber"),
        pk=pk,
    )
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Reason is required to end a subscription.")
        return redirect("subscriber_detail", pk=subscription.service.subscriber_id)
    try:
        end_subscription(
            subscription=subscription,
            reason=reason,
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Subscription ended.")
    return redirect("subscriber_detail", pk=subscription.service.subscriber_id)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.view_subscription", raise_exception=True)
@permission_required("billing.add_billingperiod", raise_exception=True)
def billing_period_activate(request, service_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=service_pk)
    form = BillingPeriodActionForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("subscriber_detail", pk=service.subscriber_id)
    try:
        activate_billing_period(
            service=service,
            operation_id=form.cleaned_data["operation_id"],
            expected_previous_period_id=form.cleaned_data["expected_previous_period_id"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Billing period activated.")
    return redirect("subscriber_detail", pk=service.subscriber_id)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.view_subscription", raise_exception=True)
@permission_required("billing.add_billingperiod", raise_exception=True)
def billing_period_renew(request, service_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=service_pk)
    form = BillingPeriodActionForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("subscriber_detail", pk=service.subscriber_id)
    try:
        renew_billing_period(
            service=service,
            operation_id=form.cleaned_data["operation_id"],
            expected_previous_period_id=form.cleaned_data["expected_previous_period_id"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Service renewed.")
    return redirect("subscriber_detail", pk=service.subscriber_id)


@login_required
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.view_subscription", raise_exception=True)
@permission_required("billing.view_billingperiod", raise_exception=True)
def billing_period_history(request, service_pk):
    service = get_object_or_404(Service.objects.select_related("subscriber"), pk=service_pk)
    periods = (
        BillingPeriod.objects.filter(service=service)
        .select_related("subscription", "previous_period")
        .order_by("-sequence_number")
    )
    paginator = Paginator(periods, 20)
    page = paginator.get_page(request.GET.get("page"))
    current_state = billing_state_for_service(service)
    return render(
        request,
        "billing/billing_period_history.html",
        {"service": service, "page": page, "current_state": current_state},
    )
