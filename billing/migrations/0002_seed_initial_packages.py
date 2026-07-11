from __future__ import annotations

from django.db import migrations


INITIAL_PACKAGES = [
    {
        "name": "5 Mbps",
        "download_speed_mbps": 5,
        "price_minor": 50000,
        "duration_days": 30,
        "grace_period_hours": 24,
        "is_active": True,
    },
    {
        "name": "15 Mbps",
        "download_speed_mbps": 15,
        "price_minor": 150000,
        "duration_days": 30,
        "grace_period_hours": 24,
        "is_active": True,
    },
    {
        "name": "30 Mbps",
        "download_speed_mbps": 30,
        "price_minor": 200000,
        "duration_days": 30,
        "grace_period_hours": 24,
        "is_active": True,
    },
]


def seed_initial_packages(apps, _schema_editor):
    plan_model = apps.get_model("billing", "Plan")
    for package in INITIAL_PACKAGES:
        if plan_model.objects.filter(name__iexact=package["name"]).exists():
            continue
        plan_model.objects.create(currency="KES", description="", **package)


def noop_reverse(_apps, _schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_packages, reverse_code=noop_reverse),
    ]
