from __future__ import annotations

from datetime import datetime, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from subscribers.models import Service, Subscriber

from .forms import (
    BillingPeriodActionForm,
    FakePaymentIngestionForm,
    LedgerReversalForm,
    PackageSearchForm,
    PaymentSearchForm,
    PlanForm,
    ResolveUnmatchedPaymentForm,
    SubscriptionPackageForm,
    WalletAdjustmentForm,
)
from .models import (
    BillingCharge,
    BillingPeriod,
    LedgerEntry,
    Payment,
    PaymentAllocation,
    Plan,
    Subscription,
    UnmatchedPaymentCase,
    Wallet,
)
from .services import (
    activate_billing_period,
    activate_service_from_wallet,
    assign_package,
    billing_state_for_service,
    change_subscription_package,
    create_package,
    end_subscription,
    ingest_fake_payment,
    post_manual_wallet_adjustment,
    renew_billing_period,
    renew_service_from_wallet,
    resolve_unmatched_payment,
    reverse_ledger_entry,
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
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.view_subscription", raise_exception=True)
@permission_required("billing.view_billingperiod", raise_exception=True)
@permission_required("billing.add_billingperiod", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
@permission_required("billing.view_billingcharge", raise_exception=True)
@permission_required("billing.add_billingcharge", raise_exception=True)
def wallet_funded_activate(request, service_pk):
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
        activate_service_from_wallet(
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
        messages.success(request, "Service activated from Wallet.")
    return redirect("subscriber_detail", pk=service.subscriber_id)


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("subscribers.view_service", raise_exception=True)
@permission_required("billing.view_subscription", raise_exception=True)
@permission_required("billing.view_billingperiod", raise_exception=True)
@permission_required("billing.add_billingperiod", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
@permission_required("billing.view_billingcharge", raise_exception=True)
@permission_required("billing.add_billingcharge", raise_exception=True)
def wallet_funded_renew(request, service_pk):
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
        renew_service_from_wallet(
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
        messages.success(request, "Service renewed from Wallet.")
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
    can_view_charge_details = (
        request.user.has_perm("billing.view_wallet")
        and request.user.has_perm("billing.view_ledgerentry")
        and request.user.has_perm("billing.view_billingcharge")
    )
    charges_by_period = {}
    if can_view_charge_details:
        charges_by_period = {
            charge.billing_period_id: charge
            for charge in BillingCharge.objects.filter(billing_period__in=page.object_list)
        }
    period_rows = [
        {"period": period, "charge": charges_by_period.get(period.pk)}
        for period in page.object_list
    ]
    return render(
        request,
        "billing/billing_period_history.html",
        {
            "service": service,
            "page": page,
            "period_rows": period_rows,
            "current_state": current_state,
            "can_view_charge_details": can_view_charge_details,
        },
    )


def _end_of_day(value):
    return timezone.make_aware(datetime.combine(value, time.max))


ALLOCATION_DETAIL_PERMISSIONS = (
    "billing.view_paymentallocation",
    "billing.view_wallet",
    "billing.view_ledgerentry",
    "subscribers.view_subscriber",
)
ALLOCATION_SEARCH_PERMISSIONS = (
    "billing.view_paymentallocation",
    "subscribers.view_subscriber",
)
FAKE_PAYMENT_PERMISSIONS = (
    "subscribers.view_subscriber",
    "billing.view_paymentproviderprofile",
    "billing.view_payment",
    "billing.add_payment",
    "billing.view_paymentallocation",
    "billing.add_paymentallocation",
    "billing.view_wallet",
    "billing.view_ledgerentry",
    "billing.add_ledgerentry",
)
UNMATCHED_RESOLUTION_PERMISSIONS = (
    "subscribers.view_subscriber",
    "billing.view_payment",
    "billing.view_paymentallocation",
    "billing.add_paymentallocation",
    "billing.view_unmatchedpaymentcase",
    "billing.change_unmatchedpaymentcase",
    "billing.view_wallet",
    "billing.view_ledgerentry",
    "billing.add_ledgerentry",
)


def _has_permissions(user, permissions: tuple[str, ...]) -> bool:
    return all(user.has_perm(permission) for permission in permissions)


@login_required
@permission_required("billing.view_payment", raise_exception=True)
def payment_list(request):
    form = PaymentSearchForm(request.GET)
    can_search_allocation_subscribers = _has_permissions(
        request.user,
        ALLOCATION_SEARCH_PERMISSIONS,
    )
    if not can_search_allocation_subscribers:
        form.fields["q"].widget.attrs["placeholder"] = "Transaction ID or account reference"
    payments = (
        Payment.objects.select_related("provider_profile")
        .annotate(
            has_allocation=Exists(
                PaymentAllocation.objects.filter(payment_id=OuterRef("pk"))
            )
        )
        .order_by("-received_at", "-created_at")
    )
    query = ""
    status = ""
    provider_profile = None
    date_from = None
    date_to = None
    if form.is_valid():
        query = form.cleaned_data["q"].strip()
        status = form.cleaned_data["status"]
        provider_profile = form.cleaned_data["provider_profile"]
        date_from = form.cleaned_data["date_from"]
        date_to = form.cleaned_data["date_to"]
        if query:
            query_filter = Q(provider_transaction_id__icontains=query) | Q(
                account_reference__icontains=query
            )
            if can_search_allocation_subscribers:
                query_filter |= Q(
                    allocations__wallet__subscriber__account_number__icontains=query
                )
            payments = payments.filter(query_filter).distinct()
        if provider_profile is not None:
            payments = payments.filter(provider_profile=provider_profile)
        if date_from is not None:
            payments = payments.filter(received_at__date__gte=date_from)
        if date_to is not None:
            payments = payments.filter(received_at__lte=_end_of_day(date_to))
        if status == "allocated":
            payments = payments.filter(allocations__isnull=False)
        elif status == "unmatched":
            payments = payments.filter(allocations__isnull=True)
    paginator = Paginator(payments, 20)
    page = paginator.get_page(request.GET.get("page"))
    fake_form_visible = (
        settings.SUPERSURF_ENVIRONMENT != "PRODUCTION"
        and _has_permissions(request.user, FAKE_PAYMENT_PERMISSIONS)
    )
    can_view_unmatched_payment_cases = request.user.has_perm("billing.view_unmatchedpaymentcase")
    return render(
        request,
        "billing/payment_list.html",
        {
            "form": form,
            "page": page,
            "query": query,
            "status": status,
            "provider_profile": provider_profile,
            "date_from": date_from,
            "date_to": date_to,
            "fake_form_visible": fake_form_visible,
            "can_view_unmatched_payment_cases": can_view_unmatched_payment_cases,
            "can_search_allocation_subscribers": can_search_allocation_subscribers,
        },
    )


@login_required
@permission_required("billing.view_payment", raise_exception=True)
def payment_detail(request, pk):
    payment = get_object_or_404(Payment.objects.select_related("provider_profile"), pk=pk)
    has_allocation = PaymentAllocation.objects.filter(payment=payment).exists()
    can_view_allocation_details = _has_permissions(
        request.user,
        ALLOCATION_DETAIL_PERMISSIONS,
    )
    allocation = None
    if can_view_allocation_details:
        allocation = (
            PaymentAllocation.objects.select_related(
                "wallet",
                "wallet__subscriber",
                "ledger_entry",
                "created_by",
            )
            .filter(payment=payment)
            .first()
        )
    can_view_unmatched_case = request.user.has_perm("billing.view_unmatchedpaymentcase")
    unmatched_case = None
    if can_view_unmatched_case:
        unmatched_case = (
            UnmatchedPaymentCase.objects.select_related(
                "resolved_wallet",
                "resolution_allocation",
            )
            .filter(payment=payment)
            .first()
        )
    can_resolve_unmatched = (
        unmatched_case is not None
        and unmatched_case.status == UnmatchedPaymentCase.STATUS_OPEN
        and _has_permissions(request.user, UNMATCHED_RESOLUTION_PERMISSIONS)
    )
    return render(
        request,
        "billing/payment_detail.html",
        {
            "payment": payment,
            "has_allocation": has_allocation,
            "allocation": allocation,
            "unmatched_case": unmatched_case,
            "can_view_allocation_details": can_view_allocation_details,
            "can_view_unmatched_case": can_view_unmatched_case,
            "can_resolve_unmatched": can_resolve_unmatched,
        },
    )


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("billing.view_paymentproviderprofile", raise_exception=True)
@permission_required("billing.add_payment", raise_exception=True)
@permission_required("billing.view_payment", raise_exception=True)
@permission_required("billing.view_paymentallocation", raise_exception=True)
@permission_required("billing.add_paymentallocation", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
def fake_payment_create(request):
    if settings.SUPERSURF_ENVIRONMENT == "PRODUCTION":
        messages.error(request, "Fake payment ingestion is not available in production.")
        return redirect("payment_list")
    if request.method == "POST":
        form = FakePaymentIngestionForm(request.POST)
        if form.is_valid():
            try:
                payment = ingest_fake_payment(
                    provider_profile=form.cleaned_data["provider_profile"],
                    provider_transaction_id=form.cleaned_data["provider_transaction_id"],
                    amount=form.cleaned_data["amount_ksh"],
                    received_at=form.cleaned_data["received_at"],
                    account_reference=form.cleaned_data["account_reference"],
                    operation_id=form.cleaned_data["operation_id"],
                    actor=request.user,
                    payload_digest=form.cleaned_data["payload_digest"],
                    request=request,
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Fake payment ingested.")
                return redirect("payment_detail", pk=payment.pk)
    else:
        form = FakePaymentIngestionForm(initial={"received_at": timezone.now()})
    return render(request, "billing/fake_payment_form.html", {"form": form})


@login_required
@permission_required("billing.view_payment", raise_exception=True)
@permission_required("billing.view_unmatchedpaymentcase", raise_exception=True)
def unmatched_payment_list(request):
    cases = (
        UnmatchedPaymentCase.objects.select_related("payment", "payment__provider_profile")
        .order_by("status", "-opened_at")
    )
    paginator = Paginator(cases, 20)
    page = paginator.get_page(request.GET.get("page"))
    can_resolve_unmatched = _has_permissions(request.user, UNMATCHED_RESOLUTION_PERMISSIONS)
    return render(
        request,
        "billing/unmatched_payment_list.html",
        {"page": page, "can_resolve_unmatched": can_resolve_unmatched},
    )


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("billing.view_unmatchedpaymentcase", raise_exception=True)
@permission_required("billing.change_unmatchedpaymentcase", raise_exception=True)
@permission_required("billing.view_payment", raise_exception=True)
@permission_required("billing.view_paymentallocation", raise_exception=True)
@permission_required("billing.add_paymentallocation", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
def unmatched_payment_resolve(request, pk):
    unmatched_case = get_object_or_404(
        UnmatchedPaymentCase.objects.select_related("payment", "payment__provider_profile"),
        pk=pk,
    )
    if request.method == "POST":
        form = ResolveUnmatchedPaymentForm(request.POST)
        if form.is_valid():
            try:
                allocation = resolve_unmatched_payment(
                    unmatched_case=unmatched_case,
                    subscriber=form.cleaned_data["subscriber"],
                    operation_id=form.cleaned_data["operation_id"],
                    reason=form.cleaned_data["reason"],
                    actor=request.user,
                    request=request,
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Unmatched payment resolved.")
                return redirect("payment_detail", pk=allocation.payment_id)
    else:
        form = ResolveUnmatchedPaymentForm()
    return render(
        request,
        "billing/unmatched_payment_resolve.html",
        {"case": unmatched_case, "form": form},
    )


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
def wallet_detail(request, subscriber_pk):
    subscriber = get_object_or_404(Subscriber, pk=subscriber_pk)
    wallet = Wallet.objects.filter(subscriber=subscriber).first()
    latest_entry = None
    entries = LedgerEntry.objects.none()
    balance_display = "KSh 0"
    if wallet is not None:
        entries = (
            wallet.entries.select_related(
                "created_by",
                "reverses_entry",
                "billing_charge",
                "billing_charge__service",
                "payment_allocation",
                "payment_allocation__payment",
                "payment_allocation__payment__provider_profile",
            )
            .order_by("-sequence_number")
        )
        latest_entry = entries.first()
        balance_display = wallet.formatted_balance
    paginator = Paginator(entries, 20)
    page = paginator.get_page(request.GET.get("page"))
    can_view_service_references = request.user.has_perm("subscribers.view_service")
    can_view_payment = request.user.has_perm("billing.view_payment")
    entry_rows = []
    for entry in page.object_list:
        service_reference = ""
        payment_reference = ""
        if can_view_service_references and entry.entry_type == LedgerEntry.ENTRY_BILLING_CHARGE:
            try:
                service_reference = entry.billing_charge.service.service_reference
            except BillingCharge.DoesNotExist:
                service_reference = ""
        if can_view_payment and entry.entry_type == LedgerEntry.ENTRY_PAYMENT_CREDIT:
            try:
                payment_reference = entry.payment_allocation.payment.provider_transaction_id
            except PaymentAllocation.DoesNotExist:
                payment_reference = ""
        entry_rows.append(
            {
                "entry": entry,
                "reversal_form": LedgerReversalForm(),
                "service_reference": service_reference,
                "payment_reference": payment_reference,
                "is_reversal": entry.entry_type == LedgerEntry.ENTRY_REVERSAL,
                "is_reversible": entry.is_reversible,
                "is_reversed": LedgerEntry.objects.filter(reverses_entry=entry).exists(),
            }
        )
    can_add_ledger_entry = request.user.has_perm("billing.add_ledgerentry")
    credit_form = WalletAdjustmentForm(
        initial={"direction": LedgerEntry.DIRECTION_CREDIT},
    )
    debit_form = WalletAdjustmentForm(
        initial={"direction": LedgerEntry.DIRECTION_DEBIT},
    )
    return render(
        request,
        "billing/wallet_detail.html",
        {
            "subscriber": subscriber,
            "wallet": wallet,
            "balance_display": balance_display,
            "latest_entry": latest_entry,
            "page": page,
            "entry_rows": entry_rows,
            "can_add_ledger_entry": can_add_ledger_entry,
            "credit_form": credit_form,
            "debit_form": debit_form,
        },
    )


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
def wallet_adjustment(request, subscriber_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    subscriber = get_object_or_404(Subscriber, pk=subscriber_pk)
    form = WalletAdjustmentForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("wallet_detail", subscriber_pk=subscriber.pk)
    try:
        entry = post_manual_wallet_adjustment(
            subscriber=subscriber,
            direction=form.cleaned_data["direction"],
            amount=form.cleaned_data["amount_ksh"],
            operation_id=form.cleaned_data["operation_id"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"Wallet {entry.get_direction_display().lower()} posted.")
    return redirect("wallet_detail", subscriber_pk=subscriber.pk)


@login_required
@permission_required("subscribers.view_subscriber", raise_exception=True)
@permission_required("billing.view_wallet", raise_exception=True)
@permission_required("billing.view_ledgerentry", raise_exception=True)
@permission_required("billing.add_ledgerentry", raise_exception=True)
def ledger_entry_reverse(request, entry_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    entry = get_object_or_404(
        LedgerEntry.objects.select_related("wallet", "wallet__subscriber"),
        pk=entry_pk,
    )
    form = LedgerReversalForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("wallet_detail", subscriber_pk=entry.wallet.subscriber_id)
    try:
        reverse_ledger_entry(
            entry=entry,
            operation_id=form.cleaned_data["operation_id"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Ledger entry reversed.")
    return redirect("wallet_detail", subscriber_pk=entry.wallet.subscriber_id)
