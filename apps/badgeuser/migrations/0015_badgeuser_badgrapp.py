# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-10-31 17:13


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mainsite", "0012_badgrapp_public_pages_redirect"),
        ("badgeuser", "0014_badgraccesstoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="badgeuser",
            name="badgrapp",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="mainsite.BadgrApp",
            ),
        ),
    ]
