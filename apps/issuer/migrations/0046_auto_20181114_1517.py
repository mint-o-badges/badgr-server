# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-11-14 23:17


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0045_auto_20181104_1847"),
    ]

    operations = [
        migrations.AlterField(
            model_name="badgeclass",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="badgeinstance",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="issuer",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
