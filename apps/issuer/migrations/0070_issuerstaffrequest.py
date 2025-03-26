# Generated by Django 3.2 on 2025-03-25 19:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('issuer', '0069_delete_learningpathparticipant'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssuerStaffRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_version', models.PositiveIntegerField(default=1)),
                ('entity_id', models.CharField(default=None, max_length=254, unique=True)),
                ('requestedOn', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(default='Pending', max_length=254)),
                ('revoked', models.BooleanField(db_index=True, default=False)),
                ('issuer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staffrequests', to='issuer.issuer')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
