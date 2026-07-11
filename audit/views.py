from __future__ import annotations

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import AuditEvent


@login_required
@permission_required("audit.view_auditevent", raise_exception=True)
def audit_log(request):
    query = request.GET.get("q", "").strip()
    events = AuditEvent.objects.select_related("actor")
    if query:
        events = events.filter(
            Q(action__icontains=query)
            | Q(target_type__icontains=query)
            | Q(target_identifier__icontains=query)
            | Q(correlation_id__icontains=query)
        )
    paginator = Paginator(events, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "audit/audit_log.html", {"page": page, "query": query})

