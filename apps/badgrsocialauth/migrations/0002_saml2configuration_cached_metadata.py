# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-07-02 01:10


from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("badgrsocialauth", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="saml2configuration",
            name="cached_metadata",
            field=models.TextField(
                blank=True,
                default=b"",
                help_text=b"If the XML is provided here we avoid making a network request to the metadata_conf_url.",
            ),
        ),
    ]
