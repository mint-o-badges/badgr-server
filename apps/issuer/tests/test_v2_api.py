# encoding: utf-8


import time
import urllib.request
import urllib.parse
import urllib.error
from urllib.parse import urlparse

from django.urls import reverse
from django.test import override_settings

from mainsite.tests import SetupIssuerHelper, BadgrTestCase, BadgeUser
from mainsite.models import AccessTokenProxy, AccessTokenScope
from oauth2_provider.models import Application
from django.utils import timezone
from datetime import timedelta
from badgeuser.models import UserRecipientIdentifier


@override_settings(
    CELERY_ALWAYS_EAGER=True
)
class AssertionsChangedSinceTests(SetupIssuerHelper, BadgrTestCase):
    def verify_email(self, user):
        email = user.cached_emails()[0]
        email.verified = True
        email.primary = True
        email.save()

    def test_with_two_apps(self):
        # Application A
        client_a = BadgeUser.objects.create(email="danger@example.com",
                                        first_name="Danger No No",
                                        last_name="No",
                                        create_email_address=True,
                                        send_confirmation=False)
        self.verify_email(client_a)
        app_a = Application.objects.create(
            client_id='client_a', client_secret='secret', authorization_grant_type='client-credentials',
            user=client_a)
        token_a = AccessTokenProxy.objects.create(
            user=client_a, scope="r:assertions", expires=timezone.now() + timedelta(hours=1),
            token='prettyplease1', application=app_a
        )

        # Application B
        client_b = BadgeUser.objects.create(email="yes@example.com",
                                        first_name="Gimme Yes",
                                        last_name="Yes Yes Yes",
                                        create_email_address=True,
                                        send_confirmation=False)
        self.verify_email(client_b)
        app_b = Application.objects.create(
            client_id='client_b', client_secret='secret', authorization_grant_type='client-credentials',
            user=client_b)
        token_b = AccessTokenProxy.objects.create(
            user=client_b, scope="r:assertions", expires=timezone.now() + timedelta(hours=1),
            token='prettyplease2', application=app_b
        )

        user = BadgeUser.objects.create(email="recipient@example.com",
                                        first_name="Firsty",
                                        last_name="Lastington",
                                        create_email_address=True,
                                        send_confirmation=False)
        self.verify_email(user)
        # token for app b with r:backpack
        AccessTokenProxy.objects.create(
            user=user, scope="r:backpack", expires=timezone.now() + timedelta(hours=1),
            token='prettyplease3', application=app_b
        )
        # token for app a with r:profile
        AccessTokenProxy.objects.create(
            user=user, scope="r:profile", expires=timezone.now() + timedelta(hours=1),
            token='prettyplease4', application=app_a
        )
        staff = self.setup_user(email="staff@example.com", authenticate=False)
        issuer = self.setup_issuer(name="Giver", owner=staff)
        badge = self.setup_badgeclass(issuer=issuer)
        badge.issue(recipient_id="recipient@example.com")

        # Application A should not have access to the badge instance
        self.client.credentials(HTTP_AUTHORIZATION='Bearer {}'.format(token_a.token))
        url = reverse('v2_api_assertions_changed_list')
        response = self.client.get(url)
        self.assertEqual(len(response.data['result']), 0)

        # Application B should *not* have access to the badge instance as per update in BP-2347
        self.client.credentials(HTTP_AUTHORIZATION='Bearer {}'.format(token_b.token))
        url = reverse('v2_api_assertions_changed_list')
        response = self.client.get(url)
        self.assertEqual(len(response.data['result']), 0)

    def test_application_can_fetch_changed_assertions(self):
        # as per update in BP-2347, this token should not be able to get anything anymore
        staff = self.setup_user(email='staff@example.com')
        recipient = self.setup_user(email='recipient@example.com', authenticate=False)
        unrelated_recipient = self.setup_user(email='otherrecipient1@example.com')

        issuer = self.setup_issuer(owner=staff)
        badgeclass = self.setup_badgeclass(issuer=issuer)
        badgeclass.issue(recipient_id=recipient.email)
        badgeclass.issue(recipient_id=staff.email)
        badgeclass.issue(recipient_id=unrelated_recipient.email)
        url = reverse('v2_api_assertions_changed_list')

        clientAppUser = self.setup_user(email='clientApp@example.com', token_scope='r:assertions')
        app = Application.objects.create(
            client_id='clientApp-authcode', client_secret='testsecret', authorization_grant_type='authorization-code',
            user=clientAppUser)
        AccessTokenProxy.objects.create(
            user=staff, scope='rw:issuer r:profile r:backpack', expires=timezone.now() + timedelta(hours=1),
            token='123', application=app
        )
        token = AccessTokenProxy.objects.create(
            user=recipient, scope='rw:issuer r:profile r:backpack', expires=timezone.now() + timedelta(hours=1),
            token='abc2', application=app
        )
        # Sanity check that signal was called post AbstractAccessToken save()
        self.assertEqual(AccessTokenScope.objects.filter(token=token).count(), 3)

        unrelated_app = Application.objects.create(
            client_id='clientApp-authcode-2', client_secret='testsecret', authorization_grant_type='authorization-code',
            user=None)
        AccessTokenProxy.objects.create(
            user=unrelated_recipient, scope='rw:issuer r:profile r:backpack', expires=timezone.now() + timedelta(hours=1),
            token='abc3', application=unrelated_app
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def assertions_in_expected_order_through_pagination(self):
        staff = self.setup_user(email='staff@example.com', token_scope='r:issuer')
        recipient = self.setup_user(email='recipient@example.com', authenticate=False)
        issuer = self.setup_issuer(owner=staff)
        badgeclass = self.setup_badgeclass(issuer=issuer)

        assertions = []
        for n in range(5):
            assertions.append(badgeclass.issue(recipient_id=recipient.email))

        cut_time = urllib.parse.quote(timezone.now().isoformat())
        time.sleep(0.1)

        for n in range(10):
            assertions.append(badgeclass.issue(recipient_id=recipient.email))

        response = self.client.get(reverse('v2_api_assertions_changed_list') + '?num=5&since={}'.format(cut_time))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 5)  # There are the expected number of results in a page
        self.assertEqual(response.data['result'][0]['entityId'], assertions[5].entity_id)
        self.assertEqual(response.data['result'][4]['entityId'], assertions[9].entity_id)

        next_url = urlparse(response.data['pagination']['nextResults'])
        response = self.client.get("?".join([next_url.path, next_url.query]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 5)  # There are the expected number of results in a page
        self.assertEqual(response.data['result'][0]['entityId'], assertions[10].entity_id)
        self.assertEqual(response.data['result'][4]['entityId'], assertions[14].entity_id)


class AssertionFetching(SetupIssuerHelper, BadgrTestCase):
    def test_can_paginate_fetch_assertions_by_recipient(self):
        user1 = self.setup_user(authenticate=True, email='user1@example.com')
        user2 = self.setup_user(email='user2@example.com')
        user3 = self.setup_user(email='user3@example.com')
        issuer = self.setup_issuer(owner=user1)
        badgeclass = self.setup_badgeclass(issuer=issuer)

        badgeclass.issue(recipient_id=user1.email)
        badgeclass.issue(recipient_id=user2.email)
        badgeclass.issue(recipient_id=user3.email)

        url = "{url}?num=2&recipient={email3}".format(
            url=reverse('v2_api_badgeclass_assertion_list',
                        kwargs={'entity_id': badgeclass.entity_id}),
            email3=user3.email
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

    def test_can_fetch_assertions_by_recipient_ids_for_badgeclass(self):
        user1 = self.setup_user(authenticate=True, email='user1@example.com')
        user2 = self.setup_user(email='user2@example.com')
        user3 = self.setup_user(email='user3@example.com')
        issuer = self.setup_issuer(owner=user1)
        badgeclass = self.setup_badgeclass(issuer=issuer)

        badgeclass.issue(recipient_id=user1.email)
        badgeclass.issue(recipient_id=user2.email)
        badgeclass.issue(recipient_id=user3.email)

        # Test default case without any filtering
        url = "{url}".format(
            url=reverse('v2_api_badgeclass_assertion_list', kwargs={'entity_id': badgeclass.entity_id}),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 3)

        # Filter for 1 recipient
        url = "{url}?recipient={email2}".format(
            url=reverse('v2_api_badgeclass_assertion_list', kwargs={'entity_id': badgeclass.entity_id}),
            email2=user2.email
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

        # Filter for 2 recipient
        url = "{url}?recipient={email2}&recipient={email3}".format(
            url=reverse('v2_api_badgeclass_assertion_list', kwargs={'entity_id': badgeclass.entity_id}),
            email2=user2.email,
            email3=user3.email
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

    def test_can_fetch_assertions_by_recipient_ids(self):
        user1 = self.setup_user(authenticate=True, email='user1@example.com')
        user2 = self.setup_user(email='user2@example.com')
        user3 = self.setup_user(email='user3@example.com')
        issuer = self.setup_issuer(owner=user1)
        badgeclass = self.setup_badgeclass(issuer=issuer)

        badgeclass.issue(recipient_id=user1.email)
        badgeclass.issue(recipient_id=user2.email)
        badgeclass.issue(recipient_id=user3.email)

        # Test default case without any filtering
        url = "{url}".format(
            url=reverse('v2_api_issuer_assertion_list', kwargs={'entity_id': issuer.entity_id}),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 3)

        # Filter for 1 recipient
        url = "{url}?recipient={email2}".format(
            url=reverse('v2_api_issuer_assertion_list', kwargs={'entity_id': issuer.entity_id}),
            email2=user2.email
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

        # Filter for 2 recipient
        url = "{url}?recipient={email2}&recipient={email3}".format(
            url=reverse('v2_api_issuer_assertion_list', kwargs={'entity_id': issuer.entity_id}),
            email2=user2.email,
            email3=user3.email
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

    def test_can_fetch_assertions_by_url_based_recipient_ids(self):
        url_recipient = "http://example.com"
        u1 = self.setup_user(authenticate=True, email="hey@example.com")
        UserRecipientIdentifier.objects.create(identifier=url_recipient, user=u1)
        UserRecipientIdentifier.objects.create(identifier="http://example.com/notme", user=u1)
        i = self.setup_issuer(owner=u1)
        b = self.setup_badgeclass(issuer=i)
        b.issue(recipient_id=url_recipient)
        b.issue(recipient_id=u1.email)
        b.issue(recipient_id="http://example.com/notme")
        url = "{url}?recipient={url_recipient}".format(
            url=reverse('v2_api_badgeclass_assertion_list', kwargs={'entity_id': b.entity_id}),
            url_recipient=url_recipient
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)


class AssertionPosting(SetupIssuerHelper, BadgrTestCase):
    def test_can_post_assertion_to_v2_api_badgeclass_assertion_list_with_issuer_specified(self):
        u1 = self.setup_user(authenticate=True, email="hey@example.com")
        u2 = self.setup_user(authenticate=False, email="secondIssuerUser@example.com")
        u3 = self.setup_user(authenticate=False, email="reandom3rdUser@example.com")
        i = self.setup_issuer(owner=u1)
        i2 = self.setup_issuer(owner=u2)
        b = self.setup_badgeclass(issuer=i)
        url = "{url}".format(
            url=reverse('v2_api_badgeclass_assertion_list', kwargs={'entity_id': b.entity_id})
        )
        response = self.client.post(url, data={
            "issuer": i.entity_id,
            "recipient": {
                "identity": u1.email,
                "hashed": True,
                "type": "email"
            }
        }, format="json")
        self.assertEqual(response.status_code, 201)

        # put a bad value in the issuer of the payload and make sure it is ignored
        response2 = self.client.post(url, data={
            "issuer": i2.entity_id,
            "recipient": {
                "identity": u2.email,
                "hashed": True,
                "type": "email"
            }
        }, format="json")
        self.assertEqual(response2.status_code, 201)

        # don't include issuer in request and make sure correct one is used
        response3 = self.client.post(url, data={
            "recipient": {
                "identity": u3.email,
                "hashed": True,
                "type": "email"
            }
        }, format="json")
        self.assertEqual(response3.status_code, 201)

        # fetch the assertions
        response4 = self.client.get(url)
        self.assertEqual(response4.status_code, 200)
        self.assertEqual(len(response4.data['result']), 3)
        for result in response4.data['result']:
            self.assertEqual(result['issuer'], i.entity_id)
