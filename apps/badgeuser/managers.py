import json
import random
import string

from allauth.account.adapter import get_adapter
from allauth.account.managers import EmailAddressManager
from badgeuser.authcode import encrypt_authcode
from django.conf import settings
from django.contrib.auth.models import UserManager
from django.core.exceptions import ValidationError
from django.urls import reverse
from mainsite.models import BadgrApp
from mainsite.utils import OriginSetting, set_url_query_params


class BadgeUserManager(UserManager):
    duplicate_email_error = "Account could not be created. An account with this email address may already exist."

    def create(
        self,
        email,
        first_name,
        last_name,
        request=None,
        plaintext_password=None,
        send_confirmation=True,
        create_email_address=True,
        marketing_opt_in=False,
        source="",
    ):
        from badgeuser.models import CachedEmailAddress, TermsVersion

        user = None
        badgrapp = BadgrApp.objects.get_current(request=request)

        # Do we know about this email address yet?
        try:
            existing_email = CachedEmailAddress.cached.get(email=email)
        except CachedEmailAddress.DoesNotExist:
            # nope
            pass
        else:
            if (
                plaintext_password
                and not existing_email.user.password
                and not existing_email.verified
            ):
                # yes, it's owned by an auto-created user trying to set a password
                user = existing_email.user
            elif plaintext_password and not existing_email.user.password:
                # yes, it's owned by an auto-created user trying to set a password,
                # but email was marked verified to allow this user API access from other applications
                # We shouldn't set any of the user attributes at this time until confirmation
                user = existing_email.user
                self.send_account_confirmation(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    badgrapp_id=badgrapp.id,
                    marketing_opt_in=marketing_opt_in,
                    plaintext_password=plaintext_password,
                    source=source,
                )
                return self.model(email=email)
            elif existing_email.verified:
                raise ValidationError(self.duplicate_email_error)
            else:
                # yes, it's an unverified email address owned by a claimed user
                # remove the email
                existing_email.delete()
                # if the user no longer has any emails, remove it
                if len(existing_email.user.cached_emails()) == 0:
                    existing_email.user.delete()

        if user is None:
            user = self.model(email=email)

        user.first_name = first_name
        user.last_name = last_name
        user.badgrapp = badgrapp
        user.marketing_opt_in = marketing_opt_in
        user.agreed_terms_version = TermsVersion.cached.latest_version()
        if plaintext_password:
            user.set_password(plaintext_password)
        user.save()

        # create email address record as needed
        if create_email_address:
            CachedEmailAddress.objects.add_email(
                user, email, request=request, signup=True, confirm=send_confirmation
            )
        return user

    @staticmethod
    def send_account_confirmation(**kwargs):
        if not kwargs.get("email"):
            return

        email = kwargs["email"]
        source = kwargs["source"]
        expires_seconds = getattr(settings, "AUTH_TIMEOUT_SECONDS", 7 * 86400)
        payload = kwargs.copy()
        payload["nonce"] = "".join(
            random.choice(string.ascii_uppercase) for _ in range(random.randint(20, 30))
        )
        payload = json.dumps(payload)

        authcode = encrypt_authcode(payload, expires_seconds=expires_seconds)
        confirmation_url = "{origin}{path}".format(
            origin=OriginSetting.HTTP,
            path=reverse("v2_api_account_confirm", kwargs=dict(authcode=authcode)),
        )
        if source:
            confirmation_url = set_url_query_params(confirmation_url, source=source)

        get_adapter().send_mail(
            "account/email/email_confirmation_signup",
            email,
            {
                "HTTP_ORIGIN": settings.HTTP_ORIGIN,
                "STATIC_URL": settings.STATIC_URL,
                "MEDIA_URL": settings.MEDIA_URL,
                "activate_url": confirmation_url,
                "email": email,
            },
        )


class CachedEmailAddressManager(EmailAddressManager):
    def add_email(self, user, email, request=None, confirm=False, signup=False):
        try:
            email_address = self.get(user=user, email__iexact=email)
        except self.model.DoesNotExist:
            primary = True if len(user.cached_emails()) == 0 else False
            email_address = self.create(user=user, email=email, primary=primary)
        if confirm and not email_address.verified:
            email_address.send_confirmation(request=request, signup=signup)

        # Add variant if it does not exist
        if (
            email_address.email.lower() == email.lower()
            and email_address.email != email
        ):
            self.model.add_variant(email)

        return email_address
