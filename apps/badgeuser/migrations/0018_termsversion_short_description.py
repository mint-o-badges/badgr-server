# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2018-06-12 14:09


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("badgeuser", "0017_auto_20180611_0819"),
    ]

    operations = [
        migrations.AddField(
            model_name="termsversion",
            name="short_description",
            field=models.TextField(blank=True),
        ),
    ]
