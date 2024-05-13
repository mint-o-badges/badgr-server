# Generated by Django 3.2 on 2024-05-13 12:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badgeuser', '0026_auto_20200817_1538'),
    ]

    operations = [
        migrations.AddField(
            model_name='badgeuser',
            name='mbr_user',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='badgeuser',
            name='first_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='first name'),
        ),
    ]
