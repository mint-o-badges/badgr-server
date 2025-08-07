from datetime import timedelta
import os
import random
import time
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django.core.cache.backends.filebased import FileBasedCache
from rest_framework.test import APITransactionTestCase
from badgeuser.models import BadgeUser, TermsVersion
from mainsite import TOP_DIR
from mainsite.admin import Application
from mainsite.models import AccessTokenProxy, BadgrApp


class SetupUserHelper(object):
    def setup_user(
        self,
        email=None,
        first_name="firsty",
        last_name="lastington",
        password="secret",
        authenticate=False,
        create_email_address=True,
        verified=True,
        primary=True,
        send_confirmation=False,
        token_scope=None,
        terms_version=1,
    ):
        if email is None:
            email = "setup_user_{}@email.test".format(random.random())
        user = BadgeUser.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            create_email_address=create_email_address,
            send_confirmation=send_confirmation,
        )

        if terms_version is not None:
            # ensure there are terms and the user agrees to them to ensure there are no cache misses during tests
            terms, created = TermsVersion.objects.get_or_create(version=terms_version)
            user.agreed_terms_version = terms_version
            user.save()

        if password is None:
            user.password = None  # type: ignore
        else:
            user.set_password(password)
            user.save()
        if create_email_address:
            email = user.cached_emails()[0]
            email.verified = verified
            email.primary = primary
            email.save()

        if token_scope:
            app = Application.objects.create(
                client_id="test",
                client_secret="testsecret",
                authorization_grant_type="client-credentials",  # 'authorization-code'
                user=user,
            )
            token = AccessTokenProxy.objects.create(
                user=user,
                scope=token_scope,
                expires=timezone.now() + timedelta(hours=1),
                token="prettyplease",
                application=app,
            )
            self.client.credentials(HTTP_AUTHORIZATION="Bearer {}".format(token.token))
        elif authenticate:
            self.client.force_authenticate(user=user)
        return user


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.path.join(TOP_DIR, "test.cache"),
        }
    },
)
class CachingTestCase(TransactionTestCase):
    @classmethod
    def tearDownClass(cls):
        test_cache = FileBasedCache(os.path.join(TOP_DIR, "test.cache"), {})
        test_cache.clear()

    def setUp(self):
        # scramble the cache key each time
        cache.key_prefix = "test{}".format(str(time.time()))
        super(CachingTestCase, self).setUp()


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    SESSION_ENGINE="django.contrib.sessions.backends.cache",
    HTTP_ORIGIN="http://localhost:8000",
)
class BadgrTestCase(SetupUserHelper, APITransactionTestCase, CachingTestCase):
    def setUp(self):
        super(BadgrTestCase, self).setUp()

        try:
            self.badgr_app = BadgrApp.objects.get(is_default=True)
        except BadgrApp.DoesNotExist:
            self.badgr_app = BadgrApp.objects.create(
                is_default=True, name="test cors", cors="localhost:8000"
            )
