# -*- coding: utf-8 -*-


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0007_auto_20151117_1555"),
    ]

    operations = [
        migrations.AlterField(
            model_name="badgeclass",
            name="issuer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="badgeclasses",
                to="issuer.Issuer",
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="badgeinstance",
            name="badgeclass",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="badgeinstances",
                to="issuer.BadgeClass",
            ),
            preserve_default=True,
        ),
    ]
