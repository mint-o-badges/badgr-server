# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.core.validators
import django.contrib.auth.models


class Migration(migrations.Migration):
    dependencies = [
        ("badgeuser", "0006_auto_20161128_0938"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="badgeuser",
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.AlterField(
            model_name="badgeuser",
            name="email",
            field=models.EmailField(
                max_length=254, verbose_name="email address", blank=True
            ),
        ),
        migrations.AlterField(
            model_name="badgeuser",
            name="groups",
            field=models.ManyToManyField(
                related_query_name="user",
                related_name="user_set",
                to="auth.Group",
                blank=True,
                help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                verbose_name="groups",
            ),
        ),
        migrations.AlterField(
            model_name="badgeuser",
            name="last_login",
            field=models.DateTimeField(
                null=True, verbose_name="last login", blank=True
            ),
        ),
        migrations.AlterField(
            model_name="badgeuser",
            name="username",
            field=models.CharField(
                error_messages={"unique": "A user with that username already exists."},
                max_length=30,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\w.@+-]+$",
                        "Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.",
                        "invalid",
                    )
                ],
                help_text="Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.",
                unique=True,
                verbose_name="username",
            ),
        ),
        migrations.AlterField(
            model_name="emailaddressvariant",
            name="email",
            field=models.EmailField(max_length=254),
        ),
    ]
