# Generated by Django 3.2 on 2025-04-10 21:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('issuer', '0071_issuerstaffrequest'),
    ]

    operations = [
        migrations.AlterField(
            model_name='issuerstaffrequest',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='ImportedBadgeAssertion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_version', models.PositiveIntegerField(default=1)),
                ('entity_id', models.CharField(default=None, max_length=254, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('badge_name', models.CharField(max_length=255)),
                ('badge_description', models.TextField(blank=True, null=True)),
                ('badge_criteria_url', models.URLField(blank=True, null=True)),
                ('badge_image_url', models.URLField(blank=True, null=True)),
                ('image', models.FileField(blank=True, upload_to='uploads/badges')),
                ('issuer_name', models.CharField(max_length=255)),
                ('issuer_url', models.URLField()),
                ('issuer_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('issuer_image_url', models.URLField(blank=True, null=True)),
                ('issued_on', models.DateTimeField()),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('recipient_identifier', models.CharField(db_index=True, max_length=768)),
                ('recipient_type', models.CharField(choices=[('email', 'email'), ('openBadgeId', 'openBadgeId'), ('telephone', 'telephone'), ('url', 'url')], default='email', max_length=255)),
                ('revoked', models.BooleanField(default=False)),
                ('revocation_reason', models.CharField(blank=True, max_length=255, null=True)),
                ('original_json', jsonfield.fields.JSONField()),
                ('narrative', models.TextField(blank=True, null=True)),
                ('verification_url', models.URLField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Imported Badge Assertion',
                'verbose_name_plural': 'Imported Badge Assertions',
                'ordering': ['-created_at'],
            },
        ),
    ]
