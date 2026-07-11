from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PackageSearchForm, PlanForm
from .models import Plan
from .services import create_package, set_package_active, update_package


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
    return render(request, "billing/package_detail.html", {"package": package})


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
