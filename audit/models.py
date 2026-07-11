from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=120, blank=True)
    target_identifier = models.CharField(max_length=160, blank=True)
    correlation_id = models.CharField(max_length=80, blank=True)
    safe_metadata = models.JSONField(default=dict, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    result = models.CharField(max_length=40, default="success")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        permissions = [
            ("view_security_audit", "Can view security audit events"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action}"

    def save(self, *args, **kwargs) -> None:
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            msg = "AuditEvent records are append-only through application code."
            raise RuntimeError(msg)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        msg = "AuditEvent records cannot be deleted through application code."
        raise RuntimeError(msg)
