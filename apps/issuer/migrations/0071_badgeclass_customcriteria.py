# Generated by Django 3.2 on 2025-04-02 15:07

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('issuer', '0070_badgeclass_copy_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='badgeclass',
            name='customCriteria',
            field=jsonfield.fields.JSONField(default={}),
        ),
    ]
