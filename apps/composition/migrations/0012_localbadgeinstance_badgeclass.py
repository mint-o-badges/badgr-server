# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0017_auto_20170227_1334"),
        ("composition", "0011_auto_20170227_0847"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbadgeinstance",
            name="issuer_badgeclass",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                blank=True,
                to="issuer.BadgeClass",
                null=True,
            ),
            preserve_default=True,
        ),
    ]
