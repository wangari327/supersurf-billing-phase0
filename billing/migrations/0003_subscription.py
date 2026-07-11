from __future__ import annotations

import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_seed_initial_packages"),
        ("subscribers", "0003_alter_service_label"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("ended", "Ended")],
                        default="active",
                        max_length=12,
                    ),
                ),
                ("starts_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("plan_name", models.CharField(max_length=120)),
                (
                    "download_speed_mbps",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "price_minor",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("currency", models.CharField(default="KES", editable=False, max_length=3)),
                (
                    "duration_days",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("grace_period_hours", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="billing.plan",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="subscribers.service",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["service", "status"],
                        name="billing_sub_service_status_idx",
                    ),
                    models.Index(fields=["created_at"], name="billing_sub_created_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "active")),
                        fields=("service",),
                        name="billing_subscription_one_active_per_service",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ["active", "ended"])),
                        name="billing_subscription_status_valid",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("ended_at__isnull", True), ("status", "active"))
                            | models.Q(("ended_at__isnull", False), ("status", "ended"))
                        ),
                        name="billing_subscription_status_ended_at_consistent",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("price_minor__gt", 0)),
                        name="billing_subscription_price_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("download_speed_mbps__gt", 0)),
                        name="billing_subscription_download_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("duration_days__gt", 0)),
                        name="billing_subscription_duration_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("grace_period_hours__gte", 0)),
                        name="billing_subscription_grace_non_negative",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("currency", "KES")),
                        name="billing_subscription_currency_kes",
                    ),
                ],
            },
        ),
    ]
