from badgeuser.models import TermsVersion
from mainsite.tests.base import BadgrTestCase


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
