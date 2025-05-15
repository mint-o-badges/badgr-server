# encoding: utf-8
from badgeuser.models import TermsVersion
from django.utils import timezone
from issuer.models import Issuer
from mainsite.models import AccessTokenProxy, BadgrApp
from mainsite.tests import SetupOAuth2ApplicationHelper
from mainsite.tests.base import BadgrTestCase, SetupIssuerHelper


class IssuerAdminTests(BadgrTestCase, SetupIssuerHelper, SetupOAuth2ApplicationHelper):
    def setUp(self):
        super(IssuerAdminTests, self).setUp()

        self.client_app_user = self.setup_user(
            first_name="app", email="app@example.com", token_scope="rw:serverAdmin"
        )
        self.app = self.setup_oauth2_application(
            client_id="clientApp-authcode",
            client_secret="testsecret",
            authorization_grant_type="authorization-code",
            user=self.client_app_user,
            allowed_scopes="rw:serverAdmin",
        )

        self.t = AccessTokenProxy.objects.create(
            user=self.client_app_user,
            scope="rw:serverAdmin",
            expires=timezone.now() + timezone.timedelta(hours=1),
            token="123",
            application=self.app,
        )

        self.client.credentials(HTTP_AUTHORIZATION="Bearer {}".format(self.t.token))

        self.latest_terms = TermsVersion.objects.create(
            version=3, short_description="test terms"
        )

        self.issuer_owner_user = self.setup_user(
            email="some_cool_user@example.com", verified=True
        )
        self.issuer = self.setup_issuer(owner=self.issuer_owner_user)

    def test_can_post_and_put_issuer_with_badgrDomain(self):
        badgrapp = BadgrApp.objects.create(
            is_default=False,
            name="test 2",
            cors="example.com",
            signup_redirect="https://example.com/signup",
        )
        owner_user = self.setup_user(
            first_name="owner", email="contact@example.org", authenticate=False
        )

        issuer_data = {
            "name": "Awesome Issuer",
            "description": "An issuer of awe-inspiring credentials",
            "url": "http://example.com",
            "email": "contact@example.org",
            "badgrDomain": "example.com",
            "createdBy": owner_user.entity_id,
        }
        response = self.client.post("/v2/issuers", issuer_data)
        self.assertEqual(response.status_code, 201)

        issuer = Issuer.objects.get(entity_id=response.data["result"][0]["entityId"])
        self.assertEqual(
            response.data["result"][0]["badgrDomain"], issuer_data["badgrDomain"]
        )
        self.assertEqual(issuer.badgrapp_id, badgrapp.id)
        self.assertEqual(issuer.created_by_id, owner_user.id)

        issuer_data["badgrDomain"] = (
            "localhost:8000"  # The other BadgrApp on the system
        )
        response = self.client.put(
            "/v2/issuers/{}".format(issuer.entity_id), issuer_data
        )
        self.assertEqual(response.status_code, 200)
        issuer = Issuer.objects.get(entity_id=response.data["result"][0]["entityId"])
        self.assertEqual(
            response.data["result"][0]["badgrDomain"], issuer_data["badgrDomain"]
        )
        self.assertEqual(
            issuer.badgrapp_id, self.badgr_app.id
        )  # The BadgrApp has changed.

    def test_cannot_post_issuer_with_invalid_badgrDomain(self):
        issuer_data = {
            "name": "Awesome Issuer",
            "description": "An issuer of awe-inspiring credentials",
            "url": "http://example.com",
            "email": "contact@example.org",
            "badgrDomain": "example.com",  # does not exist
        }
        response = self.client.post("/v2/issuers", issuer_data)
        self.assertEqual(response.status_code, 400)

    def test_cannot_post_issuer_with_invalid_createdBy(self):
        issuer_data = {
            "name": "Awesome Issuer",
            "description": "An issuer of awe-inspiring credentials",
            "url": "http://example.com",
            "email": "contact@example.org",
            "createdBy": "DOESNOTEXISTMAN",
        }
        response = self.client.post("/v2/issuers", issuer_data)
        self.assertEqual(response.status_code, 400)

    def test_can_get_issuer_detail(self):
        response = self.client.get("/v2/issuers/{}".format(self.issuer.entity_id))
        self.assertEqual(response.status_code, 200)

    def test_can_get_issuer_badgeclasses_list(self):
        response = self.client.get(
            "/v2/issuers/{}/badgeclasses".format(self.issuer.entity_id)
        )
        self.assertEqual(response.status_code, 200)

    def test_can_get_badgeclass_detail(self):
        badgeclass = self.setup_badgeclass(
            issuer=self.issuer, name="Example", criteria_text="Just earn it"
        )
        response = self.client.get("/v2/badgeclasses/{}".format(badgeclass.entity_id))
        self.assertEqual(response.status_code, 200)

    def test_can_get_assertion_lists(self):
        badgeclass = self.setup_badgeclass(
            issuer=self.issuer, name="Example", criteria_text="Just earn it"
        )
        badgeclass.issue(recipient_id="someone@somewhere.com")

        # can get badgeclass-specific assertion list
        response = self.client.get(
            "/v2/badgeclasses/{}/assertions".format(badgeclass.entity_id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["result"]), 1)

        # can get issuer assertion list
        response = self.client.get(
            "/v2/issuers/{}/assertions".format(self.issuer.entity_id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["result"]), 1)

    def can_post_new_assertion(self):
        badgeclass = self.setup_badgeclass(
            issuer=self.issuer, name="Example", criteria_text="Just earn it"
        )
        award_data = {"recipient": {"identity": "test@example.com"}}
        response = self.client.post(
            "/v2/badgeclasses/{}/assertions".format(badgeclass.entity_id),
            award_data,
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def can_post_staff_v1(self):
        self.setup_user(email="some_cool_staffer@example.com", verified=True)
        staff_action = {
            "action": "add",
            "email": "some_cool_staffer@example.com",
            "role": "editor",
        }
        staff_url = "/v1/issuer/issuers/{}/staff".format(self.issuer.entity_id)
        response = self.client.post(staff_url, staff_action, format="json")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(staff_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        response = self.client.get("/v2/issuers/{}".format(self.issuer.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["result"][0]["staff"]), 2)
