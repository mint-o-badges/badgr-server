# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-07-11 20:26


from django.db import migrations
import django.db.models.manager


class Migration(migrations.Migration):
    dependencies = [
        ("backpack", "0003_backpackcollection_assertions"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="backpackcollection",
            managers=[
                ("cached", django.db.models.manager.Manager()),
            ],
        ),
    ]
