from badgeuser.models import EmailAddressVariant, TermsVersion
from django.urls import reverse
from django.utils import timezone
from mainsite.models import AccessTokenProxy, ApplicationInfo
from mainsite.tests import BadgrTestCase, SetupIssuerHelper
from oauth2_provider.models import Application, RefreshToken


class AccessTokenHandling(SetupIssuerHelper, BadgrTestCase):
    def test_token_deletion(self):
        staff = self.setup_user(email="staff@example.com", authenticate=True)
        client_app_user = self.setup_user(
            email="clientApp@example.com", token_scope="r:assertions"
        )
        app = Application.objects.create(
            client_id="clientApp-authcode",
            client_secret="testsecret",
            authorization_grant_type="authorization-code",
            user=client_app_user,
        )
        ApplicationInfo.objects.create(
            application=app,
            allowed_scopes="r:assertions",
            trust_email_verification=True,
        )

        t = AccessTokenProxy.objects.create(
            user=staff,
            scope="rw:issuer r:profile r:backpack",
            expires=timezone.now() + timezone.timedelta(hours=1),
            token="123",
            application=app,
        )
        RefreshToken.objects.create(
            access_token=t, user_id=staff.pk, application_id=app.pk
        )
        url = reverse("v2_api_access_token_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["result"]), 1)
        # Delete tokens in response
        url = reverse(
            "v2_api_access_token_detail",
            kwargs={"entity_id": response.data["result"][0]["entityId"]},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(RefreshToken.objects.all()), 0)


class TermsVersionTests(BadgrTestCase):
    def test_get_latest_terms_version(self):
        self.assertEqual(TermsVersion.objects.count(), 0)
        response = self.client.get("/v2/termsVersions/latest")
        self.assertEqual(response.status_code, 404)

        latest = TermsVersion.cached.create(version=1, short_description="test data")
        response = self.client.get("/v2/termsVersions/latest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["result"][0]["shortDescription"], latest.short_description
        )


class UserProfileTests(BadgrTestCase):
    def test_get_user_profile_with_email_variants(self):
        user = self.setup_user(email="bobby@example.com", authenticate=True)
        response = self.client.get("/v2/users/self")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"][0]["emails"][0]["caseVariants"], [])
        email = user.cached_emails().first()
        EmailAddressVariant.objects.create(
            canonical_email=email, email="BOBBY@example.com"
        )
        response = self.client.get("/v2/users/self")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["result"][0]["emails"][0]["caseVariants"],
            ["BOBBY@example.com"],
        )
