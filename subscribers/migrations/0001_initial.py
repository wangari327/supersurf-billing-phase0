from __future__ import annotations

import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="Subscriber",
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
                    "account_number",
                    models.CharField(
                        editable=False,
                        max_length=8,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Subscriber account number must use the SS000001 format.",
                                regex="^SS\\d{6}$",
                            )
                        ],
                    ),
                ),
                (
                    "customer_type",
                    models.CharField(
                        choices=[("individual", "Individual"), ("business", "Business")],
                        max_length=20,
                    ),
                ),
                ("display_name", models.CharField(max_length=160)),
                ("primary_phone", models.CharField(max_length=16)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["account_number"]},
        ),
        migrations.CreateModel(
            name="SubscriberSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=80, unique=True)),
                (
                    "next_value",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Subscriber allocation sequence",
                "verbose_name_plural": "Subscriber allocation sequences",
                "ordering": ["key"],
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="Service",
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
                    "service_number",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(99),
                        ]
                    ),
                ),
                (
                    "service_reference",
                    models.CharField(
                        editable=False,
                        max_length=11,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Service reference must use the SS000001-01 format.",
                                regex="^SS\\d{6}-\\d{2}$",
                            )
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "subscriber",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="services",
                        to="subscribers.subscriber",
                    ),
                ),
            ],
            options={
                "ordering": ["subscriber__account_number", "service_number"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("subscriber", "service_number"),
                        name="subscribers_service_number_per_subscriber_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("service_number__gte", 1), ("service_number__lte", 99)),
                        name="subscribers_service_number_1_99",
                    ),
                ],
            },
        ),
    ]
