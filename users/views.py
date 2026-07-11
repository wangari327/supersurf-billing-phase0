from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from audit.service import record_event

from .forms import RoleAssignmentForm, StaffProfileForm, StaffSearchForm
from .models import User
from .services import assign_roles_to_user


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
        form = RoleAssignmentForm(request.POST, actor=request.user)
        if form.is_valid():
            try:
                assign_roles_to_user(
                    actor=request.user,
                    request=request,
                    target_user=staff_user,
                    roles=form.cleaned_data["roles"],
                    reason=form.cleaned_data["reason"],
                    current_session_key=(
                        request.session.session_key
                        if staff_user.pk == request.user.pk
                        else None
                    ),
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if staff_user.pk == request.user.pk:
                    request.session.flush()
                    messages.success(request, "Staff roles updated. Please sign in again.")
                    return redirect("login")
                messages.success(request, "Staff roles updated.")
                return redirect("staff_detail", pk=staff_user.pk)
    else:
        form = RoleAssignmentForm(initial={"roles": staff_user.groups.all()}, actor=request.user)
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
