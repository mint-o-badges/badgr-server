from allauth.socialaccount.providers.azure.provider import AzureProvider
from urllib.parse import parse_qs, urlparse
from allauth.socialaccount.providers.linkedin_oauth2.provider import LinkedInOAuth2Provider
from allauth.tests import MockedResponse, mocked_response

from django.shortcuts import reverse
from django.test import override_settings

from badgeuser.models import CachedEmailAddress

from .base import BadgrOAuth2TestsMixin, BadgrSocialAuthTestCase, DoesNotSendVerificationEmailMixin


class LinkedInOAuth2ProviderTests(DoesNotSendVerificationEmailMixin,
        BadgrOAuth2TestsMixin, BadgrSocialAuthTestCase):
    provider_id = LinkedInOAuth2Provider.id

    def get_mocked_response(self):
        email_response = MockedResponse(200,
                """{"elements": [{"handle": "urn:li:emailAddress:319371470",
               "handle~": {"emailAddress": "larry.exampleton@example.com"}}]}""")
        email_response.ok = True

        profile_response = MockedResponse(200, """{
            "profilePicture": {
                "displayImage": "urn:li:digitalmediaAsset:12345abcdefgh-12abcd"
            },
            "id": "3735408165",
            "lastName": {
                "preferredLocale": {
                    "language": "en",
                    "country": "US"
                },
                "localized": {
                    "en_US": "Exampleton"
                }
            },
            "firstName": {
                "preferredLocale": {
                    "language": "en",
                    "country": "US"
                },
                "localized": {
                    "en_US": "Larry"
                }
            }
        }""")
        profile_response.ok = True

        return [email_response, profile_response]

    def login(self, resp_mock, process='login',
              with_refresh_token=True):
        resp = self.client.get(reverse(self.provider.id + '_login'),
                               dict(process=process))
        p = urlparse(resp['location'])
        q = parse_qs(p.query)
        complete_url = reverse(self.provider.id + '_callback')
        self.assertGreater(q['redirect_uri'][0]
                           .find(complete_url), 0)
        response_json = self \
            .get_login_response_json(with_refresh_token=with_refresh_token)
        with mocked_response(
                MockedResponse(
                    200,
                    response_json,
                    {'content-type': 'application/json'}),
                *resp_mock):  # supports multiple mocks
            resp = self.client.get(complete_url,
                                   {'code': 'test',
                                    'state': q['state'][0]})
        return resp

    def test_legacy_user_can_sign_in(self):
        """
        Users who signed up for an account at an older point in time may have had the email not automatically verified,
        They should still be able to sign in.
        """
        with override_settings(SOCIALACCOUNT_PROVIDERS={self.provider.id: {'VERIFIED_EMAIL': True}}):
            # Create account the normal way
            self.login(self.get_mocked_response())
            self.client.logout()
            response = self.login(self.get_mocked_response())
            self.assert_login_redirect(response)

            # Manipulate the email to put it in the problem state
            email = CachedEmailAddress.objects.last()
            email.verified = False
            email.save()

            self.client.logout()
            response = self.login(self.get_mocked_response())
            self.assert_login_redirect(response)  # User can sign in again properly

            email_again = CachedEmailAddress.objects.last()
            self.assertTrue(email_again.verified)


class AzureProviderTests(DoesNotSendVerificationEmailMixin, BadgrOAuth2TestsMixin, BadgrSocialAuthTestCase):
    provider_id = AzureProvider.id

    def get_mocked_response(self):
        response = MockedResponse(200, """
        {"displayName": "John Smith", "mobilePhone": null,
        "preferredLanguage": "en-US", "jobTitle": "Director",
        "userPrincipalName": "john@smith.com",
        "@odata.context":
        "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
        "officeLocation": "Paris", "businessPhones": [],
        "mail": "john@smith.com", "surname": "Smith",
        "givenName": "John", "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        """)
        response.ok = True
        return response
