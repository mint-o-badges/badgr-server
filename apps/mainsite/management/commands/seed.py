from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.badgeuser.models import CachedEmailAddress, TermsVersion
from apps.mainsite.models import ApplicationInfo, BadgrApp

User = get_user_model()


class Command(BaseCommand):
    """Seed your development database for talking with local fronturl"""

    help = "Seed your database for local development"

    defaults = {
        "--username": "root",
        "--email": "root@example.com",
        "--password": "12345678",
        "--fronturl": "http://localhost:4200",
    }

    def add_arguments(self, parser):
        # print(self.defaults)
        for flag, default_val in list(self.defaults.items()):
            parser.add_argument(
                flag, nargs="?", type=str, help="Defaults to: {}".format(default_val)
            )

    def handle(self, *args, **options):
        variables = {
            "username": options["username"] or self.defaults["--username"],
            "email": options["email"] or self.defaults["--email"],
            "password": options["password"] or self.defaults["--password"],
            "fronturl": options["fronturl"] or self.defaults["--fronturl"],
        }

        # Create a super user and verify the email:
        try:
            User.objects.create_superuser(
                username=variables["username"],
                email=variables["email"],
                password=variables["password"],
            )
            CachedEmailAddress.objects.create(
                email=variables["email"], user_id=1, verified=True, primary=True
            )

            # Setup an Application, initial Terms Summary and a BadgrApp:
            a = ApplicationInfo.objects.create(
                name="dev",
                client_id="public",
                client_type="public",
                redirect_uris=variables["fronturl"] + "",
                authorization_grant_type="password",
            )
            ApplicationInfo.objects.create(
                allowed_scopes="rw:profile rw:issuer rw:backpack", application=a
            )
            TermsVersion.objects.create(
                is_active=True,
                version="1",
                short_description="This is a summary of our terms of service.",
            )
            BadgrApp.objects.create(
                name="dev",
                cors="localhost",
                email_confirmation_redirect=variables["fronturl"] + "/login",
                signup_redirect=variables["fronturl"] + "/signup",
                forgot_password_redirect=variables["fronturl"] + "/forgot-password/",
                ui_login_redirect=variables["fronturl"] + "/login/",
                ui_signup_success_redirect=variables["fronturl"] + "/signup/success/",
                ui_connect_success_redirect=variables["fronturl"] + "/profile/",
                public_pages_redirect=variables["fronturl"] + "/public",
                oauth_authorization_redirect=variables["fronturl"]
                + "/auth/oauth2/authorize",
                oauth_application=a,
            )
        except Exception:
            self.stdout.write(
                "\nSomething went wrong. ./manage.py flush and try again.\n\n"
            )
            return

        summary = (
            """
            superuser:    %(username)s
            email:        %(email)s
            password:     %(password)s
            frontend url: %(fronturl)s

            Oopsy? Want to revert?

            ./manage.py flush

            """
            % variables
        )

        self.stdout.write(summary)
