from allauth.account.signals import email_confirmed, user_signed_up
from django.apps import AppConfig
from django.db.models.signals import post_save

from .signals import handle_email_created, log_email_confirmed, log_user_signed_up


class BadgeUserConfig(AppConfig):
    name = "badgeuser"

    def ready(self):
        user_signed_up.connect(log_user_signed_up, dispatch_uid="user_signed_up")
        email_confirmed.connect(log_email_confirmed, dispatch_uid="email_confirmed")

        from allauth.account.models import EmailAddress

        post_save.connect(
            handle_email_created, sender=EmailAddress, dispatch_uid="email_created"
        )

        from mainsite.models import AccessTokenProxy
        from mainsite.signals import handle_token_save
        from oauth2_provider.models import AccessToken

        post_save.connect(
            handle_token_save, sender=AccessToken, dispatch_uid="token_saved"
        )
        post_save.connect(
            handle_token_save, sender=AccessTokenProxy, dispatch_uid="token_proxy_saved"
        )
