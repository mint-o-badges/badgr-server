# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-12-04 20:36


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0037_auto_20171113_1015"),
    ]

    operations = [
        migrations.AddField(
            model_name="badgeinstance",
            name="expires_at",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
