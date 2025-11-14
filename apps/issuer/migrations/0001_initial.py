# -*- coding: utf-8 -*-


from django.db import models, migrations
import autoslug.fields

# import jsonfield.fields
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BadgeClass",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("json", models.JSONField()),
                ("name", models.CharField(max_length=255)),
                ("slug", autoslug.fields.AutoSlugField(unique=True, max_length=255)),
                ("criteria_text", models.TextField(null=True, blank=True)),
                ("image", models.ImageField(upload_to=b"uploads/badges", blank=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="BadgeInstance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("json", models.JSONField()),
                ("email", models.EmailField(max_length=255)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        unique=True, max_length=255, editable=False
                    ),
                ),
                ("image", models.ImageField(upload_to=b"issued/badges", blank=True)),
                ("revoked", models.BooleanField(default=False)),
                (
                    "revocation_reason",
                    models.CharField(
                        default=None, max_length=255, null=True, blank=True
                    ),
                ),
                (
                    "badgeclass",
                    models.ForeignKey(
                        related_name="assertions",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="issuer.BadgeClass",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Issuer",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("json", models.JSONField()),
                ("name", models.CharField(max_length=1024)),
                ("slug", autoslug.fields.AutoSlugField(unique=True, max_length=255)),
                ("image", models.ImageField(upload_to=b"uploads/issuers", blank=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        related_name="owner",
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="IssuerStaff",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("editor", models.BooleanField(default=False)),
                (
                    "badgeuser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "issuer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="issuer.Issuer"
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="issuer",
            name="staff",
            field=models.ManyToManyField(
                to=settings.AUTH_USER_MODEL, through="issuer.IssuerStaff"
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="badgeinstance",
            name="issuer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assertions",
                to="issuer.Issuer",
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="badgeclass",
            name="issuer",
            field=models.ForeignKey(
                related_name="badgeclasses",
                on_delete=django.db.models.deletion.PROTECT,
                to="issuer.Issuer",
            ),
            preserve_default=True,
        ),
    ]
