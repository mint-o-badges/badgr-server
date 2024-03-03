# Generated by Django 2.2.28 on 2024-03-03 18:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('issuer', '0069_collectionbadgeinstance'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='collectionbadgeinstance',
            name='original_json',
        ),
        migrations.RemoveField(
            model_name='collectionbadgeinstance',
            name='source',
        ),
        migrations.RemoveField(
            model_name='collectionbadgeinstance',
            name='source_url',
        ),
        migrations.AddField(
            model_name='collectionbadgecontainer',
            name='issuer',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='collectionbadgeclasses', to='issuer.Issuer'),
            preserve_default=False,
        ),
    ]
