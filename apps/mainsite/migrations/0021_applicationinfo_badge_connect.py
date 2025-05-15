# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mainsite", "0020_auto_20191114_1056"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationinfo",
            name="logo_uri",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="applicationinfo",
            name="policy_uri",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="applicationinfo",
            name="software_id",
            field=models.CharField(blank=True, default=None, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="applicationinfo",
            name="software_version",
            field=models.CharField(blank=True, default=None, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="applicationinfo",
            name="terms_uri",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="applicationinfo",
            name="issue_refresh_token",
            field=models.BooleanField(default=True),
        ),
    ]
