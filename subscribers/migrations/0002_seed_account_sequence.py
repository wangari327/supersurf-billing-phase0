from __future__ import annotations

from django.db import migrations


def seed_account_sequence(apps, schema_editor) -> None:
    sequence_model = apps.get_model("subscribers", "SubscriberSequence")
    sequence_model.objects.get_or_create(
        key="subscriber_account",
        defaults={"next_value": 1},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("subscribers", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_account_sequence, migrations.RunPython.noop),
    ]
