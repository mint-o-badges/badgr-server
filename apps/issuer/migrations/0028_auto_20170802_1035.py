# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-02 17:35


from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0027_auto_20170801_1636"),
    ]

    operations = [
        migrations.AlterField(
            model_name="badgeinstance",
            name="issued_on",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
