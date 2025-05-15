# -*- coding: utf-8 -*-


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0009_badgeinstance_acceptance"),
        ("composition", "0006_auto_20160928_0648"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbadgeinstancecollection",
            name="issuer_instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="issuer.BadgeInstance",
                null=True,
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="localbadgeinstancecollection",
            name="collection",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="badges",
                to="composition.Collection",
            ),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="localbadgeinstancecollection",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="composition.LocalBadgeInstance",
                null=True,
            ),
            preserve_default=True,
        ),
    ]
    if settings.DATABASES["default"].get("ENGINE", "") != "sql_server.pyodbc":
        # only include this migration if not sql server, it doesn't like it.
        operations += [
            migrations.AlterUniqueTogether(
                name="localbadgeinstancecollection",
                unique_together=set([("instance", "issuer_instance", "collection")]),
            )
        ]
