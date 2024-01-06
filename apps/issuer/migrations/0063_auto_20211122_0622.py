# Generated by Django 2.2.24 on 2021-11-22 14:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('issuer', '0062_issuer_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='issuer',
            name='city',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='issuer',
            name='country',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='issuer',
            name='street',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='issuer',
            name='streetnumber',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='issuer',
            name='zip',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]