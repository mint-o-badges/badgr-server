from allauth.tests import MockedResponse

from ..tests.base import (
    BadgrOAuthTestsMixin,
    BadgrSocialAuthTestCase,
    DoesNotSendVerificationEmailMixin,
)
from .provider import KonyProvider


class KonyProviderTests(
    DoesNotSendVerificationEmailMixin, BadgrOAuthTestsMixin, BadgrSocialAuthTestCase
):
    provider_id = KonyProvider.id

    def get_mocked_response(self):
        # inferred by looking at KonyProvider implementation
        return [
            MockedResponse(
                200,
                """
            {
              "primary_email": "raymond.penners@intenct.nl",
              "first_name": "Raymond",
              "user_guid": "ZLARGMFT1M",
              "last_name": "Penners"
            }""",
            )
        ]
