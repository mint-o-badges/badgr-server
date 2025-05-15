# -*- coding: utf-8 -*-


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("issuer", "0023_auto_20170531_1044"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackpackCollection",
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
                ("entity_version", models.PositiveIntegerField(default=1)),
                (
                    "entity_id",
                    models.CharField(default=None, unique=True, max_length=254),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.CharField(max_length=255, blank=True)),
                ("share_hash", models.CharField(max_length=255, blank=True)),
                (
                    "slug",
                    models.CharField(
                        default=None, max_length=254, null=True, blank=True
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
        ),
        migrations.CreateModel(
            name="BackpackCollectionBadgeInstance",
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
                (
                    "badgeinstance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="issuer.BadgeInstance",
                    ),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="backpack.BackpackCollection",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="BackpackBadgeShare",
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
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.CharField(
                        max_length=254,
                        choices=[
                            (b"facebook", b"Facebook"),
                            (b"linkedin", b"LinkedIn"),
                        ],
                    ),
                ),
                (
                    "badgeinstance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="issuer.BadgeInstance",
                        null=True,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="BackpackCollectionShare",
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
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.CharField(
                        max_length=254,
                        choices=[
                            (b"facebook", b"Facebook"),
                            (b"linkedin", b"LinkedIn"),
                        ],
                    ),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="backpack.BackpackCollection",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
