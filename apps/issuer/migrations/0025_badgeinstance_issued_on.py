# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-07-26 21:09


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0024_auto_20170609_0845"),
    ]

    operations = [
        migrations.AddField(
            model_name="badgeinstance",
            name="issued_on",
            field=models.DateTimeField(null=True),
        ),
    ]
