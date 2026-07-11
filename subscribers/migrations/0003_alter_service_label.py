from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscribers", "0002_seed_account_sequence"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="label",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
