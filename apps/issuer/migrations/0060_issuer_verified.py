# Generated by Django 2.2.24 on 2021-09-23 10:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0059_remove_issuer_image_preview"),
    ]

    operations = [
        migrations.AddField(
            model_name="issuer",
            name="verified",
            field=models.BooleanField(default=False),
        ),
    ]
