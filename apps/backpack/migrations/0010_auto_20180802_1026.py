# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-02 17:26


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backpack", "0009_auto_20180119_0711"),
    ]

    operations = [
        migrations.AlterField(
            model_name="backpackbadgeshare",
            name="provider",
            field=models.CharField(
                choices=[
                    (b"twitter", b"Twitter"),
                    (b"facebook", b"Facebook"),
                    (b"linkedin", b"LinkedIn"),
                    (b"pinterest", b"Pinterest"),
                ],
                max_length=254,
            ),
        ),
        migrations.AlterField(
            model_name="backpackcollectionshare",
            name="provider",
            field=models.CharField(
                choices=[
                    (b"twitter", b"Twitter"),
                    (b"facebook", b"Facebook"),
                    (b"linkedin", b"LinkedIn"),
                    (b"pinterest", b"Pinterest"),
                ],
                max_length=254,
            ),
        ),
    ]
