import json

from allauth.socialaccount.models import SocialAccount, SocialApp
from badgrsocialauth.models import Saml2Account, Saml2Configuration
from badgrsocialauth.providers.twitter.tests import MOCK_TWITTER_PROFILE_RESPONSE
from django.contrib.sites.models import Site
from mainsite.tests import BadgrTestCase, SetupUserHelper


class SocialAccountV2APITests(BadgrTestCase, SetupUserHelper):
    def setUp(self):
        super(SocialAccountV2APITests, self).setUp()
        site = Site.objects.first()
        self.socialapplication = SocialApp.objects.create(
            provider="twitter",
            name="Twitter OAuth2",
            client_id="fake",
            secret="also fake",
        )
        self.socialapplication.sites.add(site)

        self.examplesamlconfig = Saml2Configuration.objects.create(
            metadata_conf_url="https://example.com/saml2conf", slug="saml2.example"
        )

    def _basic_api_requests(self):
        # have a user already authenticated on the self.client with preferred method.

        response = self.client.get("/v2/socialaccounts")
        self.assertEqual(response.status_code, 200)
        account_id = response.data.get("result")[0]["id"]
        self.assertEqual(
            response.data["result"][0]["url"], "https://twitter.com/pennersr"
        )
        self.assertEqual(response.data["result"][0]["firstName"], None)
        self.assertEqual(response.data["result"][0]["lastName"], None)
        self.assertEqual(response.data["result"][0]["primaryEmail"], None)

        response = self.client.get("/v2/socialaccounts/{}".format(account_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["result"][0]["url"], "https://twitter.com/pennersr"
        )
        self.assertEqual(response.data["result"][0]["firstName"], None)
        self.assertEqual(response.data["result"][0]["lastName"], None)
        self.assertEqual(response.data["result"][0]["primaryEmail"], None)

        response = self.client.delete("/v2/socialaccounts/{}".format(account_id))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_can_get_socialaccounts_list_view_and_detail_operations(self):
        user = self.setup_user(authenticate=True)

        SocialAccount.objects.create(
            user=user,
            provider="twitter",
            uid="123",
            extra_data=json.loads(MOCK_TWITTER_PROFILE_RESPONSE),
        )
        samlaccount = Saml2Account.objects.create(
            user=user, config=self.examplesamlconfig, uuid="abc123"
        )

        self._basic_api_requests()
        response = self.client.get(
            "/v2/socialaccounts/{}".format(samlaccount.account_identifier)
        )
        self.assertEqual(response.status_code, 200)

    def test_socialaccount_basic_operations_with_oauth_token_scope(self):
        user = self.setup_user(authenticate=True, token_scope="rw:profile")

        SocialAccount.objects.create(
            user=user,
            provider="twitter",
            uid="123",
            extra_data=json.loads(MOCK_TWITTER_PROFILE_RESPONSE),
        )

        self._basic_api_requests()

    def test_socialaccount_fails_on_invalid_scope(self):
        user = self.setup_user(authenticate=True, token_scope="rw:issuer")

        response = self.client.get("/v2/socialaccounts")
        self.assertEqual(response.status_code, 404)

        socialaccount = SocialAccount.objects.create(
            user=user,
            provider="twitter",
            uid="123",
            extra_data=json.loads(MOCK_TWITTER_PROFILE_RESPONSE),
        )
        response = self.client.get("/v2/socialaccounts/{}".format(socialaccount.id))
        self.assertEqual(response.status_code, 404)

        response = self.client.delete("/v2/socialaccounts/{}".format(socialaccount.id))
        self.assertEqual(response.status_code, 404)
