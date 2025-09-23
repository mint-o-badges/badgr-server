from mainsite.tests.base import BadgrTestCase
from badgeuser.models import EmailAddressVariant
import json


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

    def test_can_create_modify_and_delete_user_preference(self):
        self.setup_user(email="bobby@example.com", authenticate=True)

        post_response = self.client.post(
            "/v3/user/preferences/",
            data=json.dumps({"key": "bar", "value": "[1,2,3]"}),
            content_type="application/json",
        )
        get_response = self.client.get("/v3/user/preferences/bar/")
        update_response = self.client.post(
            "/v3/user/preferences/",
            data=json.dumps({"key": "bar", "value": "[1,2,3,4]"}),
            content_type="application/json",
        )
        get2_response = self.client.get("/v3/user/preferences/bar/")
        delete_response = self.client.delete("/v3/user/preferences/bar/")
        get3_response = self.client.get("/v3/user/preferences/bar/")

        self.assertEqual(post_response.status_code, 201)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.content, b'{"key":"bar","value":"[1,2,3]"}')
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(get2_response.status_code, 200)
        self.assertEqual(get2_response.content, b'{"key":"bar","value":"[1,2,3,4]"}')
        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(get3_response.status_code, 404)
