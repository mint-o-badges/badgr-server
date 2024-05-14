# Generated by Django 3.2 on 2024-05-14 11:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL),
        ('mainsite', '0024_auto_20200608_0452'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessTokenSessionId',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sessionId', models.CharField(max_length=255)),
                ('token', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL, unique=True)),
            ],
        ),
    ]
