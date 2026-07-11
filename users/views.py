from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from audit.service import record_event

from .forms import RoleAssignmentForm, StaffProfileForm, StaffSearchForm
from .models import User
from .services import invalidate_user_sessions


@login_required
@permission_required("users.view_user", raise_exception=True)
def staff_list(request):
    form = StaffSearchForm(request.GET)
    users = User.objects.order_by("username").prefetch_related("groups")
    query = ""
    if form.is_valid():
        query = form.cleaned_data["q"]
        if query:
            users = users.filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(display_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
    paginator = Paginator(users, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "users/staff_list.html", {"form": form, "page": page, "query": query})


@login_required
@permission_required("users.view_user", raise_exception=True)
def staff_detail(request, pk: int):
    staff_user = get_object_or_404(User.objects.prefetch_related("groups"), pk=pk)
    form = StaffProfileForm(instance=staff_user)
    return render(request, "users/staff_detail.html", {"staff_user": staff_user, "form": form})


@login_required
@permission_required("users.assign_roles", raise_exception=True)
def assign_roles(request, pk: int):
    staff_user = get_object_or_404(User.objects.prefetch_related("groups"), pk=pk)
    if request.method == "POST":
        form = RoleAssignmentForm(request.POST)
        if form.is_valid():
            old_roles = list(staff_user.groups.order_by("name").values_list("name", flat=True))
            staff_user.groups.set(form.cleaned_data["roles"])
            new_roles = list(staff_user.groups.order_by("name").values_list("name", flat=True))
            removed_sessions = invalidate_user_sessions(staff_user.pk)
            record_event(
                action="staff.roles.changed",
                request=request,
                target_type="user",
                target_identifier=staff_user.pk,
                metadata={
                    "old_roles": old_roles,
                    "new_roles": new_roles,
                    "removed_sessions": removed_sessions,
                },
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Staff roles updated.")
            return redirect("staff_detail", pk=staff_user.pk)
    else:
        form = RoleAssignmentForm(initial={"roles": staff_user.groups.all()})
    return render(request, "users/assign_roles.html", {"staff_user": staff_user, "form": form})


class AuditedPasswordChangeView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        record_event(
            action="password.changed",
            request=self.request,
            target_type="user",
            target_identifier=form.user.pk,
        )
        return response


audited_password_change = login_required(AuditedPasswordChangeView.as_view())

