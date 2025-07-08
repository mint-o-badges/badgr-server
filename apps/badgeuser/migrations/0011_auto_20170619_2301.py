# -*- coding: utf-8 -*-


from django.db import migrations
import badgeuser.managers


class Migration(migrations.Migration):
    dependencies = [
        ("badgeuser", "0010_merge"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="badgeuser",
            managers=[
                ("objects", badgeuser.managers.BadgeUserManager()),
            ],
        ),
    ]
