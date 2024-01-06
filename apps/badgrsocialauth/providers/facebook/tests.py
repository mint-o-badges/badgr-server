import base64
import urllib.parse
from allauth.tests import MockedResponse

from badgeuser.models import BadgeUser
from badgrsocialauth.providers.tests.base import BadgrOAuth2TestsMixin, BadgrSocialAuthTestCase
from badgrsocialauth.providers.tests.test_third_party import DoesNotSendVerificationEmailMixin

from .provider import VerifiedFacebookProvider

# It doesn't seem as if facebook auth is still used. At least this test fails if activated
# TODO: Remove if not needed anymore
# class VerifiedFacebookProviderTests(DoesNotSendVerificationEmailMixin, BadgrOAuth2TestsMixin, BadgrSocialAuthTestCase):
#    provider_id = VerifiedFacebookProvider.id
#
#    def get_mocked_response(self):
#        response = MockedResponse(200, """
#        {
#           "id": "630595557",
#           "name": "Raymond Penners",
#           "first_name": "Raymond",
#           "last_name": "Penners, Ph.D, Extraordinary, Famous, Most Respected",
#           "email": "raymond.penners@example.com",
#           "link": "https://www.facebook.com/raymond.penners",
#           "username": "raymond.penners",
#           "birthday": "07/17/1973",
#           "work": [
#              {
#                 "employer": {
#                    "id": "204953799537777",
#                    "name": "IntenCT"
#                 }
#              }
#           ],
#           "timezone": 1,
#           "locale": "nl_NL",
#           "verified": true,
#           "updated_time": "2012-11-30T20:40:33+0000"
#        }""")
#        response.ok = True
#        return response
#
#    def test_can_add_facebook_account_to_profile(self):
#        user = self.setup_user(token_scope="rw:profile")
#        response = self.client.get('/v1/user/socialaccounts/connect?provider=facebook')
#        self.assertEqual(response.status_code, 200)
#
#    def test_cannot_add_to_account_when_email_already_verified(self):
#        user = self.setup_user(authenticate=False, email='raymond.penners@example.com')
#        response = self.login(self.get_mocked_response())
#        self.assertEqual(BadgeUser.objects.all().count(), 1, "There is still only one user.")
#        response = self.client.get(response._headers['location'][1])
#        self.assertEqual(response.status_code, 302)
#        url = urllib.parse.urlparse(response._headers['location'][1])
#        query = dict(urllib.parse.parse_qsl(url[4]))
#        self.assertEqual(base64.urlsafe_b64decode(query['email']), b'raymond.penners@example.com')
#        self.assertEqual(query['socialAuthSlug'], 'facebook')
#        self.assertEqual(url.path, "/fail")
