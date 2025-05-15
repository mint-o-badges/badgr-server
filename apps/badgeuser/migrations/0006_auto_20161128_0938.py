# -*- coding: utf-8 -*-


from allauth.account.adapter import get_adapter
from allauth.account.models import EmailConfirmation
from badgeuser.models import BadgeUser, CachedEmailAddress, EmailConfirmation
from django.db import IntegrityError, migrations, models, transaction


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
