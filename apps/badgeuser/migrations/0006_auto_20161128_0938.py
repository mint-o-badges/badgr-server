# -*- coding: utf-8 -*-


from django.db import migrations


def do_nothing(apps, schema_editor):
    """
    Replaced with a management task.
    """
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("badgeuser", "0005_auto_20160901_1537"),
    ]

    operations = [migrations.RunPython(do_nothing)]
