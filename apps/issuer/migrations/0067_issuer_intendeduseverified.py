# Generated by Django 3.2 on 2024-10-28 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('issuer', '0066_qrcode_requestedbadge'),
    ]

    operations = [
        migrations.AddField(
            model_name='issuer',
            name='intendedUseVerified',
            field=models.BooleanField(default=False),
        ),
    ]
