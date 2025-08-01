# Generated by Django 2.2.18 on 2021-03-02 19:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("issuer", "0057_add_image_preview"),
    ]

    operations = [
        migrations.AlterField(
            model_name="badgeclass",
            name="slug",
            field=models.CharField(
                blank=True, db_index=True, default=None, max_length=255, null=True
            ),
        ),
        migrations.AlterField(
            model_name="badgeinstance",
            name="slug",
            field=models.CharField(
                blank=True, db_index=True, default=None, max_length=255, null=True
            ),
        ),
        migrations.AlterField(
            model_name="issuer",
            name="image_preview",
            field=models.FileField(blank=True, null=True, upload_to="uploads/issuers"),
        ),
        migrations.AlterField(
            model_name="issuer",
            name="slug",
            field=models.CharField(
                blank=True, db_index=True, default=None, max_length=255, null=True
            ),
        ),
    ]
