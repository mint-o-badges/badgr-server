# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-01-07 00:21


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("externaltools", "0007_auto_20190319_1111"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externaltool",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="externaltooluseractivation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
