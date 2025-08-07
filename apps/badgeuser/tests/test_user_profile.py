from mainsite.tests.base import BadgrTestCase
from badgeuser.models import EmailAddressVariant


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
