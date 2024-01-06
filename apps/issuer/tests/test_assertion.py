# encoding: utf-8


import datetime
from time import sleep

import dateutil.parser
import json
from openbadges_bakery import unbake
import png
import pytz
import re
from urllib.parse import quote_plus

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.test import override_settings
from oauth2_provider.models import Application

from badgeuser.models import CachedEmailAddress, UserRecipientIdentifier
from issuer.models import BadgeInstance, EmailBlacklist, IssuerStaff, Issuer
from issuer.utils import parse_original_datetime
from mainsite.tests import BadgrTestCase, SetupIssuerHelper, SetupOAuth2ApplicationHelper
from mainsite.utils import OriginSetting, hash_for_image
from rest_framework import serializers


@override_settings(BADGE_ASSERTION_AUTO_REBAKE_BATCH_SIZE=1)
class AssertionTests(SetupIssuerHelper, BadgrTestCase):
    def test_local_pending(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        award = test_badgeclass.issue(recipient_id="nobody@example.com")
        self.assertEqual(award.pending, False)

    def test_assertion_pagination(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        total_assertion_count = 25
        per_page = 10

        for i in range(0, total_assertion_count):
            test_badgeclass.issue(recipient_id='test3@unittest.concentricsky.com')

        def _parse_link_header(link_header):
            link_re = re.compile(r'<(?P<url>[^>]+)>; rel="(?P<name>[^"]+)"')
            ret = {}
            for match in link_re.findall(link_header):
                url, name = match
                ret[name] = url
            return ret

        page_number = 0
        number_seen = 0
        more_pages_present = True
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badgeclass}/assertions?num={per_page}'.format(
            issuer=test_issuer.entity_id,
            badgeclass=test_badgeclass.entity_id,
            per_page=per_page
        ))
        while more_pages_present:
            self.assertEqual(response.status_code, 200)

            page = response.data
            expected_page_count = min(total_assertion_count - number_seen, per_page)
            self.assertEqual(len(page), expected_page_count)
            number_seen += len(page)

            link_header = response.get('Link', None)
            self.assertIsNotNone(link_header)
            links = _parse_link_header(link_header)
            if page_number != 0:
                self.assertTrue('prev' in list(links.keys()))

            if number_seen < total_assertion_count:
                self.assertTrue('next' in list(links.keys()))
                next_url = links.get('next')
                response = self.client.get(next_url)
                page_number += 1
            else:
                more_pages_present = False

    def test_can_rebake_assertion(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_assertion = test_badgeclass.issue(recipient_id='test1@email.test')
        data = str(unbake(test_assertion.image))

        self.assertIn('https://w3id.org/openbadges/v2', data)

        original_image_url = test_assertion.image_url()
        test_assertion.rebake()
        assertion = BadgeInstance.objects.get(entity_id=test_assertion.entity_id)
        self.assertNotEqual(original_image_url, test_assertion.image_url(),
                            "To ensure downstream caches don't have the old image saved, "
                            "a new filename is used")

        v2_datastr = unbake(assertion.image)
        self.assertTrue(v2_datastr)
        self.assertIn('https://w3id.org/openbadges/v2', v2_datastr)

    def test_put_rebakes_assertion(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='test1@email.test')

        # v1 api
        v1_backdate = datetime.datetime(year=2021, month=3, day=3, tzinfo=pytz.utc)
        updated_data = dict(
            expires=v1_backdate.isoformat()
        )

        response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_assertion.cached_issuer.entity_id,
            badge=test_assertion.cached_badgeclass.entity_id,
            assertion=test_assertion.entity_id
        ), updated_data)
        self.assertEqual(response.status_code, 200)
        updated_assertion = BadgeInstance.objects.get(entity_id=test_assertion.entity_id)
        updated_obo = json.loads(str(unbake(updated_assertion.image)))
        self.assertEqual(updated_obo.get('expires', None), updated_data.get('expires'))

        # v2 api
        v2_backdate = datetime.datetime(year=2002, month=3, day=3, tzinfo=pytz.UTC)
        updated_data = dict(
            issuedOn=v2_backdate.isoformat()
        )

        response = self.client.put('/v2/assertions/{assertion}'.format(
            assertion=test_assertion.entity_id
        ), updated_data)
        self.assertEqual(response.status_code, 200)
        updated_assertion = BadgeInstance.objects.get(entity_id=test_assertion.entity_id)
        updated_obo = json.loads(str(unbake(updated_assertion.image)))
        self.assertEqual(updated_obo.get('issuedOn', None), updated_data.get('issuedOn'))

    def test_updating_badgeclass_image_rebakes_assertions(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass_v1 = self.setup_badgeclass(name="for v1 test", issuer=test_issuer)
        test_badgeclass_v2 = self.setup_badgeclass(name="for v2 test", issuer=test_issuer)
        test_assertion_v1 = test_badgeclass_v1.issue(recipient_id='test1@email.test')
        test_assertion_v2 = test_badgeclass_v2.issue(recipient_id='test2@email.test')
        test_assertion_v2_2 = test_badgeclass_v2.issue(recipient_id='test3@email.test')
        self.assertEqual(test_assertion_v1.image.name.split(".").pop(), 'png')
        self.assertEqual(test_assertion_v2.image.name.split(".").pop(), 'png')
        self.assertEqual(test_assertion_v2_2.image.name.split(".").pop(), 'png')

        with open(self.get_test_svg_image_path(), 'rb') as image_update:
            # v1 api
            original_image_hash_v1 = hash_for_image(test_assertion_v1.image)
            self.assertNotEqual('', original_image_hash_v1)
            response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badgeclass}'.format(
                issuer=test_assertion_v1.cached_issuer.entity_id,
                badgeclass=test_assertion_v1.cached_badgeclass.entity_id,
            ), dict(
                image=image_update,
                name=test_badgeclass_v1.name,
                description=test_badgeclass_v1.description,
                criteria_text="some criteria"
            ))
            self.assertEqual(response.status_code, 200)
            sleep(2)
            updated_assertion_v1 = BadgeInstance.objects.get(entity_id=test_assertion_v1.entity_id)
            updated_image_hash_v1 = hash_for_image(updated_assertion_v1.image)
            self.assertNotEqual('', updated_image_hash_v1)
            self.assertNotEqual(updated_image_hash_v1, original_image_hash_v1)
            self.assertGreater(updated_assertion_v1.updated_at, test_assertion_v1.updated_at)
            self.assertEqual(updated_assertion_v1.image.name.split(".").pop(), 'svg')

        with open(self.get_test_svg_image_path(), 'rb') as image_update:
            # v2 api
            original_image_hash_v2 = hash_for_image(test_assertion_v2.image)
            self.assertNotEqual('', original_image_hash_v2)
            original_image_hash_v2_2 = hash_for_image(test_assertion_v2_2.image)
            self.assertNotEqual('', original_image_hash_v2_2)
            response = self.client.put('/v2/badgeclasses/{badge}'.format(
                badge=test_assertion_v2.cached_badgeclass.entity_id
            ), dict(
                name=test_badgeclass_v2.name,
                description=test_badgeclass_v2.description,
                image=image_update
            ))
            self.assertEqual(response.status_code, 200)
            sleep(2)
            updated_assertion_v2 = BadgeInstance.objects.get(entity_id=test_assertion_v2.entity_id)
            updated_image_hash_v2 = hash_for_image(updated_assertion_v2.image)
            self.assertNotEqual('', updated_image_hash_v2)
            self.assertNotEqual(updated_image_hash_v2, original_image_hash_v2)
            self.assertGreater(updated_assertion_v2.updated_at, test_assertion_v2.updated_at)
            self.assertEqual(updated_assertion_v2.image.name.split(".").pop(), 'svg')
            response = self.client.get('/v2/assertions/{}'.format(updated_assertion_v2.entity_id))
            self.assertEqual(response.status_code, 200)
            result = response.data['result'][0]
            self.assertIn('{}/image'.format(updated_assertion_v2.entity_id), result['image'])  # canonical image url

            # test batching works in task
            updated_assertion_v2_2 = BadgeInstance.objects.get(entity_id=test_assertion_v2_2.entity_id)
            updated_image_hash_v2_2 = hash_for_image(updated_assertion_v2_2.image)
            self.assertNotEqual('', updated_image_hash_v2_2)
            self.assertNotEqual(updated_image_hash_v2_2, original_image_hash_v2_2)
            self.assertGreater(updated_assertion_v2_2.updated_at, test_assertion_v2_2.updated_at)
            self.assertEqual(updated_assertion_v2_2.image.name.split(".").pop(), 'svg')

    def test_updating_badgeclass_non_image_does_not_rebake_assertions(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass_v1 = self.setup_badgeclass(name="for v1 test", issuer=test_issuer)
        test_badgeclass_v2 = self.setup_badgeclass(name="for v2 test", issuer=test_issuer)
        test_assertion_v1 = test_badgeclass_v1.issue(recipient_id='test1@email.test')
        test_assertion_v2 = test_badgeclass_v2.issue(recipient_id='test2@email.test')

        # v1 api
        original_image_url_v1 = test_assertion_v1.image_url()
        with open(self.get_test_image_path(), 'rb') as image:
            response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_assertion_v1.cached_issuer.entity_id,
                badge=test_assertion_v1.cached_badgeclass.entity_id,
            ), dict(
                name="some name update",
                description="some description",
                criteria_text="some criteria",
                image=image
            ))
        self.assertEqual(response.status_code, 200)
        sleep(2)
        updated_assertion_v1 = BadgeInstance.objects.get(entity_id=test_assertion_v1.entity_id)
        self.assertEqual(updated_assertion_v1.image_url(), original_image_url_v1)

        # v2 api
        original_image_url_v2 = test_assertion_v2.image_url()
        with open(self.get_test_image_path(), 'rb') as image:
            response = self.client.put('/v2/badgeclasses/{badge}'.format(
                badge=test_assertion_v2.cached_badgeclass.entity_id
            ), dict(
                name="some name update 2",
                description="some description 2",
                image=image
            ))
        self.assertEqual(response.status_code, 200)
        sleep(2)
        updated_assertion_v2 = BadgeInstance.objects.get(entity_id=test_assertion_v2.entity_id)
        self.assertEqual(updated_assertion_v2.image_url(), original_image_url_v2)

        # v2 api
        original_image_url_v2 = test_assertion_v2.image_url()
        response = self.client.put('/v2/badgeclasses/{badge}'.format(
            badge=test_assertion_v2.cached_badgeclass.entity_id
        ), dict(
            name="some name update 3",
            description="some description 3"
        ))
        self.assertEqual(response.status_code, 200)
        sleep(2)
        updated_assertion_v2 = BadgeInstance.objects.get(entity_id=test_assertion_v2.entity_id)
        self.assertEqual(updated_assertion_v2.image_url(), original_image_url_v2)

    def test_can_update_assertion(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion_data = {
            "email": "test@example.com",
            "create_notification": False,
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion_data)
        self.assertEqual(response.status_code, 201)
        original_assertion = response.data

        new_assertion_data = {
            "recipient_type": "email",
            "recipient_identifier": "test@example.com",
            "narrative": "test narrative",
            "evidence_items": [{
                "narrative": "This is the evidence item narrative AGAIN!.",
                "evidence_url": ""
            }],
        }
        response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=original_assertion.get('slug'),
        ), json.dumps(new_assertion_data), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        updated_assertion = response.data
        self.assertDictContainsSubset(new_assertion_data, updated_assertion)

        # verify v2 api
        v2_assertion_data = {
            "evidence": [
                {
                    "narrative": "remove and add new narrative",
                }
            ]
        }
        response = self.client.put('/v2/assertions/{assertion}'.format(
            assertion=original_assertion.get('slug')
        ), json.dumps(v2_assertion_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        v2_assertion = data.get('result', [None])[0]
        self.assertEqual(len(v2_assertion_data['evidence']), 1)
        self.assertEqual(v2_assertion['evidence'][0]['narrative'], v2_assertion_data['evidence'][0]['narrative'])

        instance = BadgeInstance.objects.get(entity_id=original_assertion['slug'])
        image = instance.image
        image_data = json.loads(unbake(image))

        self.assertEqual(image_data.get('evidence', {})[0].get(
            'narrative'), v2_assertion_data['evidence'][0]['narrative'])

    def test_can_update_assertion_issuer(self):
        test_user = self.setup_user(authenticate=True)
        email_two = CachedEmailAddress.objects.create(email='testemail2@example.com', verified=True, user=test_user)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion_data = {
            "email": "test@example.com",
            "create_notification": False,
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion_data)
        self.assertEqual(response.status_code, 201)
        original_assertion = response.data

        response = self.client.put(
            '/v1/issuer/issuers/{issuer}'.format(issuer=test_issuer.entity_id),
            json.dumps({
                'email': email_two.email,
                'url': test_issuer.url,
                'name': test_issuer.name,
                'category': test_issuer.category
            }), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            '/public/assertions/{}?expand=badge&expand=badge.issuer'.format(original_assertion['slug']))
        assertion_data = response.data
        self.assertEqual(assertion_data['badge']['issuer']['email'], email_two.email)

    def test_can_issue_assertion_with_expiration(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        expiration = timezone.now()

        # can issue assertion with expiration
        assertion = {
            "email": "test@example.com",
            "create_notification": False,
            "expires": expiration.isoformat()
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion)
        self.assertEqual(response.status_code, 201)
        assertion_json = response.data
        self.assertEqual(dateutil.parser.parse(assertion_json.get('expires')), expiration)

        # v1 endpoint returns expiration
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=assertion_json.get('slug')
        ))
        self.assertEqual(response.status_code, 200)
        v1_json = response.data
        self.assertEqual(dateutil.parser.parse(v1_json.get('expires')), expiration)

        # v2 endpoint returns expiration
        response = self.client.get('/v2/assertions/{assertion}'.format(
            assertion=assertion_json.get('slug')
        ))
        self.assertEqual(response.status_code, 200)
        v2_json = response.data.get('result')[0]
        self.assertEqual(dateutil.parser.parse(v2_json.get('expires')), expiration)

        # public url returns expiration
        response = self.client.get(assertion_json.get('public_url'))
        self.assertEqual(response.status_code, 200)
        public_json = response.data
        self.assertEqual(dateutil.parser.parse(public_json.get('expires')), expiration)

    def test_can_issue_badge_if_authenticated(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion = {
            "email": "test@example.com",
            "create_notification": False
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion)
        self.assertEqual(response.status_code, 201)
        self.assertIn('slug', response.data)
        assertion_slug = response.data.get('slug')
        # warm the cache
        _ = test_user.verified
        _ = test_issuer.cached_issuerstaff()
        # assert that the BadgeInstance was published to and fetched from cache
        query_count = 0
        with self.assertNumQueries(query_count):
            response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
                issuer=test_issuer.entity_id,
                badge=test_badgeclass.entity_id,
                assertion=assertion_slug))
            self.assertEqual(response.status_code, 200)

    def test_can_issue_badge_by_class_name_success(self):
        badgeclass_name = "A Badge"
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)

        assertion = {
            "recipient": {
                "identity": "test@example.com"
            },
            "badgeclassName": badgeclass_name,
        }

        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertEqual(response.status_code, 201)

    def test_can_issue_badge_by_class_name_error(self):
        badgeclass_name = "A Badge"
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)

        assertion = {
            "recipient": {
                "identity": "test@example.com"
            },
            "badgeclassName": "does not exist",
        }

        self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertRaises(serializers.ValidationError)

    def test_can_issue_badge_by_class_name_cached_issuer_error(self):
        badgeclass_name = "A Badge"
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)

        assertion = {
            "recipient": {
                "identity": "test@example.com"
            },
            "badgeclassName": badgeclass_name,
        }

        # Cause issuer to be published to cache.
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertEqual(response.status_code, 201)

        # Update issuer without re-publishing to cache.
        Issuer.objects.filter(pk=test_issuer.pk).update(
            description='Using update method will not cause cache to be updated')

        # Error condition would instead produce a
        # 400 "Could not find matching badgeclass for this issuer."
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertEqual(response.status_code, 201)

    def test_can_issue_badge_by_class_ambiguity_error(self):
        badgeclass_name = "A Badge"
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)

        assertion = {
            "recipient": {
                "identity": "test@example.com"
            },
            "badgeclassName": badgeclass_name,
        }

        self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertRaises(serializers.ValidationError)

    def test_cannot_issue_badge_to_invalid_email_error(self):
        badgeclass_name = "A Badge"
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)
        self.setup_badgeclass(issuer=test_issuer, name=badgeclass_name)

        assertion = {
            "recipient": {
                "identity": "example.com",
                "type": "email"
            },
            "badgeclassName": badgeclass_name,
        }

        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), assertion, format="json")
        self.assertRaises(serializers.ValidationError)
        self.assertEqual(response.status_code, 400)

    def test_cannot_issue_email_assertion_to_non_email(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion = {
            "recipient_identifier": "example.com",
            "recipient_type": "email",
            "create_notification": True
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion)
        self.assertEqual(response.status_code, 400)

    def test_badge_recipient_notified_by_email_before_blacklisting_but_not_after(self):
        # notify_earner tries: EmailBlacklist.objects.get(email=self.recipient_identifier)
        # if a matching email is found an event is logged and the recipient is not sent an email
        # If no matching email is found recipient is sent an email

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        user_email = 'test3@example.com'
        new_assertion_props = {
            'recipient': {'identity': user_email},
            'badgeclassOpenBadgeId': test_badgeclass.jsonld_id,
            'notify': True
        }

        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)
        instance = BadgeInstance.objects.get(entity_id=response.data['result'][0]['entityId'])

        self.assertEqual(len(mail.outbox), 1)

        # No matching email is found, no logging, recipient is sent an email
        instance.notify_earner(self.badgr_app)
        self.assertEqual(len(mail.outbox), 2)

        # Matching email is found, an event is logged, recipient is not sent an email
        EmailBlacklist(email=user_email).save()
        instance.notify_earner(self.badgr_app)
        self.assertEqual(len(mail.outbox), 2)

    def test_issue_badge_with_ob1_evidence(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        evidence_url = "http://fake.evidence.url.test"
        assertion = {
            "email": "test@example.com",
            "create_notification": False,
            "evidence": evidence_url
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion)
        self.assertEqual(response.status_code, 201)

        self.assertIn('slug', response.data)
        assertion_slug = response.data.get('slug')
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=assertion_slug))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get('json'))
        self.assertEqual(response.data.get('json').get('evidence'), evidence_url)

        # ob2.0 evidence_items also present
        self.assertEqual(response.data.get('evidence_items'), [
            {
                'evidence_url': evidence_url,
                'narrative': None,
            }
        ])

    def test_issue_badge_with_ob2_multiple_evidence(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        evidence_items = [
            {
                'evidence_url': "http://fake.evidence.url.test",
            },
            {
                'evidence_url': "http://second.evidence.url.test",
                "narrative": "some description of how second evidence was collected"
            }
        ]
        assertion_args = {
            "email": "test@example.com",
            "create_notification": False,
            "evidence_items": evidence_items
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion_args, format='json')
        self.assertEqual(response.status_code, 201)

        assertion_slug = response.data.get('slug')
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=assertion_slug))
        self.assertEqual(response.status_code, 200)
        assertion = response.data

        fetched_evidence_items = assertion.get('evidence_items')
        self.assertEqual(len(fetched_evidence_items), len(evidence_items))
        for i in range(0, len(evidence_items)):
            self.assertEqual(fetched_evidence_items[i].get('url'), evidence_items[i].get('url'))
            self.assertEqual(fetched_evidence_items[i].get('narrative'), evidence_items[i].get('narrative'))

        # ob1.0 evidence url also present
        self.assertIsNotNone(assertion.get('json'))
        assertion_public_url = OriginSetting.HTTP + reverse('badgeinstance_json', kwargs={'entity_id': assertion_slug})
        self.assertEqual(assertion.get('json').get('evidence'), assertion_public_url)

    def test_v2_issue_with_evidence(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        evidence_items = [
            {
                'url': "http://fake.evidence.url.test",
            },
            {
                'url': "http://second.evidence.url.test",
                "narrative": "some description of how second evidence was collected"
            }
        ]
        assertion_args = {
            "recipient": {"identity": "test@example.com"},
            "notify": False,
            "evidence": evidence_items
        }
        response = self.client.post('/v2/badgeclasses/{badge}/assertions'.format(
            badge=test_badgeclass.entity_id
        ), assertion_args, format='json')
        self.assertEqual(response.status_code, 201)

        assertion_slug = response.data['result'][0]['entityId']
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=assertion_slug))
        self.assertEqual(response.status_code, 200)
        assertion = response.data

        v2_json = self.client.get('/public/assertions/{}?v=2_0'.format(assertion_slug), format='json').data

        fetched_evidence_items = assertion.get('evidence_items')
        self.assertEqual(len(fetched_evidence_items), len(evidence_items))
        for i in range(0, len(evidence_items)):
            self.assertEqual(v2_json['evidence'][i].get('id'), evidence_items[i].get('url'))
            self.assertEqual(v2_json['evidence'][i].get('narrative'), evidence_items[i].get('narrative'))
            self.assertEqual(fetched_evidence_items[i].get('evidence_url'), evidence_items[i].get('url'))
            self.assertEqual(fetched_evidence_items[i].get('narrative'), evidence_items[i].get('narrative'))

        # ob1.0 evidence url also present
        self.assertIsNotNone(assertion.get('json'))
        assertion_public_url = OriginSetting.HTTP + reverse('badgeinstance_json', kwargs={'entity_id': assertion_slug})
        self.assertEqual(assertion.get('json').get('evidence'), assertion_public_url)

    def test_issue_badge_with_ob2_one_evidence_item(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        evidence_items = [
            {
                'narrative': "Executed some sweet skateboard tricks that made us completely forget the badge criteria"
            }
        ]
        assertion_args = {
            "email": "test@example.com",
            "create_notification": False,
            "evidence_items": evidence_items
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion_args, format='json')
        self.assertEqual(response.status_code, 201)

        assertion_slug = response.data.get('slug')
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=assertion_slug))
        self.assertEqual(response.status_code, 200)
        assertion = response.data

        v2_json = self.client.get('/public/assertions/{}?v=2_0'.format(assertion_slug), format='json').data

        fetched_evidence_items = assertion.get('evidence_items')
        self.assertEqual(len(fetched_evidence_items), len(evidence_items))
        for i in range(0, len(evidence_items)):
            self.assertEqual(v2_json['evidence'][i].get('id'), evidence_items[i].get('url'))
            self.assertEqual(v2_json['evidence'][i].get('narrative'), evidence_items[i].get('narrative'))
            self.assertEqual(fetched_evidence_items[i].get('url'), evidence_items[i].get('url'))
            self.assertEqual(fetched_evidence_items[i].get('narrative'), evidence_items[i].get('narrative'))

        # ob1.0 evidence url also present
        self.assertIsNotNone(assertion.get('json'))
        assertion_public_url = OriginSetting.HTTP + reverse('badgeinstance_json', kwargs={'entity_id': assertion_slug})
        self.assertEqual(assertion.get('json').get('evidence'), assertion_public_url)

    def test_resized_png_image_baked_properly(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion = {
            "email": "test@example.com"
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion)
        self.assertIn('slug', response.data)
        assertion_slug = response.data.get('slug')

        instance = BadgeInstance.objects.get(entity_id=assertion_slug)

        instance.image.open()
        self.assertIsNotNone(unbake(instance.image))
        instance.image.close()
        instance.image.open()

        image_data_present = False
        badge_data_present = False
        reader = png.Reader(file=instance.image)
        for chunk in reader.chunks():
            if chunk[0] == b'IDAT':
                image_data_present = True
            elif chunk[0] == b'iTXt' and chunk[1].startswith(b'openbadges\x00\x00\x00\x00\x00'):
                badge_data_present = True

        self.assertTrue(image_data_present and badge_data_present)

    def test_authenticated_editor_can_issue_badge(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        editor_user = self.setup_user(authenticate=True)
        IssuerStaff.objects.create(
            issuer=test_issuer,
            role=IssuerStaff.ROLE_EDITOR,
            user=editor_user
        )

        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), {"email": "test@example.com"})
        self.assertEqual(response.status_code, 201)

    def test_authenticated_nonowner_user_cant_issue(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        self.setup_user(authenticate=True)
        assertion = {
            "email": "test2@example.com"
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), assertion)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_cant_issue(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion = {
            "email": "test2@example.com"
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), assertion)
        self.assertIn(response.status_code, (401, 403))

    def test_issue_assertion_with_notify(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        assertion = {
            "email": "unittest@unittesting.badgr.io",
            'create_notification': True
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), assertion)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

    def test_first_assertion_always_notifies_recipient(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        outbox_count = len(mail.outbox)

        assertion = {
            "email": "first_recipients_assertion@unittesting.badgr.io",
            'create_notification': False
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), assertion)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), outbox_count + 1)

        # should not get notified of second assertion
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), assertion)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), outbox_count + 1)

    def test_authenticated_owner_list_assertions(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(recipient_id='new.recipient@email.test')
        test_badgeclass.issue(recipient_id='second.recipient@email.test')

        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_issuer_instance_list_assertions(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(recipient_id='new.recipient@email.test')
        test_badgeclass.issue(recipient_id='second.recipient@email.test')

        response = self.client.get('/v1/issuer/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_issuer_instance_list_assertions_with_expired(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        expired_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')
        expired_assertion.expires_at = datetime.datetime.now() - datetime.timedelta(days=1)
        expired_assertion.save()
        test_badgeclass.issue(recipient_id='second.recipient@email.test')

        response = self.client.get('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

        response = self.client.get('/v2/issuers/{issuer}/assertions?include_expired=1'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

    def test_issuer_instance_list_assertions_with_revoked(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(recipient_id='new.recipient@email.test')
        revoked_assertion = test_badgeclass.issue(recipient_id='second.recipient@email.test')
        revoked_assertion.revoked = True
        revoked_assertion.save()

        response = self.client.get('/v2/issuers/{issuer}/assertions?include_revoked=1'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

        response = self.client.get('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

    def test_issuer_instance_list_assertions_with_revoked_and_expired(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(recipient_id='new.recipient@email.test')
        revoked_assertion = test_badgeclass.issue(recipient_id='second.recipient@email.test')
        revoked_assertion.revoked = True
        revoked_assertion.save()
        expired_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')
        expired_assertion.expires_at = datetime.datetime.now() - datetime.timedelta(days=1)
        expired_assertion.save()

        response = self.client.get('/v2/issuers/{issuer}/assertions?include_revoked=1&include_expired=1'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 3)

        response = self.client.get('/v2/issuers/{issuer}/assertions?include_revoked=1'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

        response = self.client.get('/v2/issuers/{issuer}/assertions?include_expired=1'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 2)

        response = self.client.get('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)

    def test_issuer_instance_list_assertions_with_id(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(recipient_id='new.recipient@email.test')
        test_badgeclass.issue(recipient_id='second.recipient@email.test')

        response = self.client.get('/v1/issuer/issuers/{issuer}/assertions?recipient=new.recipient@email.test'.format(
            issuer=test_issuer.entity_id,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_can_revoke_assertion(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        revocation_reason = 'Earner kind of sucked, after all.'

        response = self.client.delete('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=test_assertion.entity_id,
        ), {'revocation_reason': revocation_reason})
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/public/assertions/{assertion}.json'.format(assertion=test_assertion.entity_id))
        self.assertEqual(response.status_code, 200)
        assertion_obo = json.loads(response.content)
        self.assertDictContainsSubset(dict(
            revocationReason=revocation_reason,
            revoked=True
        ), assertion_obo)

    def test_can_revoke_assertion_bulk(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        revocation_data = [{
            'entityId': test_assertion.entity_id,
            'revocationReason': 'Earner kind of sucked, after all.'
        }]

        response = self.client.post(reverse('v2_api_assertion_revoke'), data=revocation_data, format='json')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/public/assertions/{assertion}.json'.format(assertion=test_assertion.entity_id))
        self.assertEqual(response.status_code, 200)
        assertion_obo = json.loads(response.content)
        self.assertDictContainsSubset(dict(
            revocationReason=revocation_data[0]['revocationReason'],
            revoked=True
        ), assertion_obo)

    def test_cannot_revoke_assertion_if_missing_reason(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.delete('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
            assertion=test_assertion.entity_id,
        ))
        self.assertEqual(response.status_code, 400)

    def test_issue_svg_badge(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        with open(self.get_test_svg_image_path(), 'rb') as svg_badge_image:
            response = self.client.post('/v1/issuer/issuers/{issuer}/badges'.format(
                issuer=test_issuer.entity_id,
            ), {
                'name': 'svg badge',
                'description': 'svg badge',
                'image': svg_badge_image,
                'criteria': 'http://wikipedia.org/Awesome',
            })
            badgeclass_slug = response.data.get('slug')

        assertion = {
            "email": "test@example.com"
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=badgeclass_slug
        ), assertion)
        self.assertEqual(response.status_code, 201)

        slug = response.data.get('slug')
        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions/{assertion}'.format(
            issuer=test_issuer.entity_id,
            badge=badgeclass_slug,
            assertion=slug
        ))
        self.assertEqual(response.status_code, 200)

    def test_new_assertion_updates_cached_user_badgeclasses(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        original_recipient_count = test_badgeclass.badgeinstances.filter(revoked=False).count()

        new_assertion_props = {
            'email': 'test3@example.com',
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ), new_assertion_props)
        self.assertEqual(response.status_code, 201)

        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id,
        ))
        response.data
        self.assertEqual(test_badgeclass.badgeinstances.filter(revoked=False).count(), original_recipient_count + 1)

    def test_batch_assertions_throws_400(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        invalid_batch_assertion_props = [
            {
                "recipient": {
                    "identity": "foo@bar.com"
                }
            }
        ]
        response = self.client.post('/v2/badgeclasses/{badge}/issue'.format(
            badge=test_badgeclass.entity_id
        ), invalid_batch_assertion_props, format='json')
        self.assertEqual(response.status_code, 400)

    def test_batch_assertions_with_invalid_issuedon(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        invalid_batch_assertion_props = {
            "assertions": [
                {
                    'recipient': {
                        "identity": "foo@bar.com",
                        "type": "email"
                    }
                },
                {
                    'recipient': {
                        "identity": "bar@baz.com",
                        "type": "email"
                    },
                    'issuedOn': 1512151153620
                },
            ]
        }
        response = self.client.post('/v2/badgeclasses/{badge}/issue'.format(
            badge=test_badgeclass.entity_id
        ), invalid_batch_assertion_props, format='json')
        self.assertEqual(response.status_code, 400)

    def test_issue_assertion_with_unacceptable_issuedOn(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        issue_time = timezone.now() + timezone.timedelta(days=1)
        assertion_data = {
            'recipient': {
                "identity": "bar@baz.com",
                "type": "email"
            },
            'issuedOn': issue_time.isoformat()
        }

        response = self.client.post('/v2/badgeclasses/{badge}/assertions'.format(
            badge=test_badgeclass.entity_id
        ), assertion_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['fieldErrors']['issuedOn'][0], 'Only issuedOn dates in the past are acceptable.')

        assertion_data['issuedOn'] = '1492-01-01T13:00:00Z'  # A time prior to introduction of the Gregorian calendar.
        response = self.client.post('/v2/badgeclasses/{badge}/assertions'.format(
            badge=test_badgeclass.entity_id
        ), assertion_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['fieldErrors']['issuedOn'][0],
                         'Only issuedOn dates after the introduction of the Gregorian calendar are allowed.')

    def test_batch_assertions_with_evidence(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        batch_assertion_props = {
            'assertions': [{
                "recipient": {
                    "identity": "foo@bar.com",
                    "type": "email",
                    "hashed": True,
                },
                "narrative": "foo@bar's test narrative",
                "evidence": [
                    {
                        "url": "http://example.com?evidence=foo.bar",
                    },
                    {
                        "url": "http://example.com?evidence=bar.baz",
                        "narrative": "barbaz"
                    }
                ]
            }],
            'create_notification': True
        }
        response = self.client.post('/v2/badgeclasses/{badge}/issue'.format(
            badge=test_badgeclass.entity_id
        ), batch_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)

        result = json.loads(response.content)
        returned_assertions = result.get('result')

        # verify results contain same evidence that was provided
        for i in range(0, len(returned_assertions)):
            expected = batch_assertion_props['assertions'][i]
            self.assertListOfDictsContainsSubset(expected.get('evidence'), returned_assertions[i].get('evidence'))

        # verify OBO returns same results
        assertion_entity_id = returned_assertions[0].get('entityId')
        expected = batch_assertion_props['assertions'][0]

        response = self.client.get('/public/assertions/{assertion}.json?v=2_0'.format(
            assertion=assertion_entity_id
        ), format='json')
        self.assertEqual(response.status_code, 200)

        assertion_obo = json.loads(response.content)

        expected = expected.get('evidence')
        evidence = assertion_obo.get('evidence')
        for i in range(0, len(expected)):
            self.assertEqual(evidence[i].get('id'), expected[i].get('url'))
            self.assertEqual(evidence[i].get('narrative', None), expected[i].get('narrative', None))

    def assertListOfDictsContainsSubset(self, expected, actual):
        for i in range(0, len(expected)):
            a = expected[i]
            b = actual[i]
            self.assertDictContainsSubset(a, b)

    def test_get_share_url(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')
        test_assertion2 = test_badgeclass.issue(recipient_id='+15035555555', recipient_type='telephone')
        test_assertion3 = test_badgeclass.issue(recipient_id='test.example.com/foo?bar=1', recipient_type='url')

        url = test_assertion.get_share_url()
        self.assertEqual(test_assertion.jsonld_id, url)
        url = test_assertion.get_share_url(include_identifier=True)
        self.assertEqual(test_assertion.jsonld_id + '?identity__email=new.recipient%40email.test', url)
        url = test_assertion2.get_share_url(include_identifier=True)
        self.assertEqual(test_assertion2.jsonld_id + '?identity__telephone=%2B15035555555', url)
        url = test_assertion3.get_share_url(include_identifier=True)
        self.assertEqual(test_assertion3.jsonld_id + '?identity__url=test.example.com/foo%3Fbar%3D1', url)

    def test_parse_original_datetime(self):
        result = parse_original_datetime('1577232000')
        self.assertEqual(result, '2019-12-25T00:00:00Z')
        result = parse_original_datetime('2018-12-23')
        self.assertEqual(result, '2018-12-23T00:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00')
        self.assertEqual(result, '2018-12-23T00:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00Z')
        self.assertEqual(result, '2018-12-23T00:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00-05:00')
        self.assertEqual(result, '2018-12-23T05:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00+05:00')
        self.assertEqual(result, '2018-12-22T19:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00+00:00')
        self.assertEqual(result, '2018-12-23T00:00:00Z')
        result = parse_original_datetime('2018-12-23T00:00:00+12:34')
        self.assertEqual(result, '2018-12-22T11:26:00Z')
        result = parse_original_datetime('2018-12-23T13:37:00+12:34')
        self.assertEqual(result, '2018-12-23T01:03:00Z')


class V2ApiAssertionTests(SetupIssuerHelper, BadgrTestCase):
    def test_v2_issue_by_badgeclassOpenBadgeId(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            },
            'badgeclassOpenBadgeId': test_badgeclass.jsonld_id
        }
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)
        result = response.data['result'][0]
        self.assertIn('{}/image'.format(result['entityId']), result['image'])  # canonical image url

    def test_v2_issue_uppercase_email(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        new_assertion_props = {
            'recipient': {
                'identity': 'TEST3@example.com'
            },
            'badgeclassOpenBadgeId': test_badgeclass.jsonld_id
        }
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)
        assertion_data = response.data['result'][0]
        recipient_id = assertion_data['recipient']['plaintextIdentity']
        self.assertEqual(
            recipient_id, new_assertion_props['recipient']['identity'].lower(),
            "Reported recipient ID is lowercase")
        assertion_from_db = BadgeInstance.objects.get(entity_id=assertion_data['entityId'])
        self.assertEqual(
            assertion_from_db.recipient_identifier, new_assertion_props['recipient']['identity'].lower(),
            "Stored recipient ID is lowercase")

    def test_v2_issue_uppercase_url(self):
        """
        Unlike emails, URLs are presumed to be case sensitive as reported to us.
        """
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        new_assertion_props = {
            'recipient': {
                'identity': 'https://eXaMpLe.CoM/UPPERCASEPATH',
                'type': 'url'
            },
            'badgeclassOpenBadgeId': test_badgeclass.jsonld_id
        }
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)

        assertion_data = response.data['result'][0]
        recipient_id = assertion_data['recipient']['plaintextIdentity']
        self.assertEqual(
            recipient_id, 'https://example.com/UPPERCASEPATH',
            "Reported recipient ID URL is not automatically lowercased")
        assertion_from_db = BadgeInstance.objects.get(entity_id=assertion_data['entityId'])
        self.assertEqual(
            assertion_from_db.recipient_identifier, 'https://example.com/UPPERCASEPATH',
            "Stored recipient ID is not automatically lowercased")

        new_assertion_props['recipient']['identity'] = 'NOTAURL/NOTAVALIDONE/butlookslikeone?sorta=True'
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['fieldErrors']['recipient']['non_field_errors'][0], 'Enter a valid URL.')
        # TODO this might be nicer if it were just a fieldError for recipient.identity
        # or just was a non_field_error:[str] to begin with

    def test_v2_issue_by_badgeclassOpenBadgeId_permissions(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        other_user = self.setup_user(authenticate=False)
        other_issuer = self.setup_issuer(owner=other_user)
        other_badgeclass = self.setup_badgeclass(issuer=other_issuer)

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            },
            'badgeclassOpenBadgeId': other_badgeclass.jsonld_id
        }
        response = self.client.post('/v2/issuers/{issuer}/assertions'.format(
            issuer=test_issuer.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 400)

    def test_v2_issue_entity_id_in_path(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            }
        }
        response = self.client.post('/v2/badgeclasses/{badgeclass}/assertions'.format(
            badgeclass=test_badgeclass.entity_id), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201)

        other_user = self.setup_user(authenticate=False)
        other_issuer = self.setup_issuer(owner=other_user)
        other_badgeclass = self.setup_badgeclass(issuer=other_issuer)

        response = self.client.post('/v2/badgeclasses/{badgeclass}/assertions'.format(
            badgeclass=other_badgeclass.entity_id), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 404)

    def test_can_revoke_assertion(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        revocation_reason = "I take it all back. I don't mean what I said when I was hungry."

        response = self.client.delete('/v2/assertions/{assertion}'.format(
            assertion=test_assertion.entity_id,
        ), {'revocation_reason': revocation_reason})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['result'][0]['revocationReason'], revocation_reason)

        response = self.client.get('/public/assertions/{assertion}.json'.format(assertion=test_assertion.entity_id))
        self.assertEqual(response.status_code, 200)
        assertion_obo = json.loads(response.content)
        self.assertDictContainsSubset(dict(
            revocationReason=revocation_reason,
            revoked=True
        ), assertion_obo)

        response = self.client.delete('/v2/assertions/{assertion}'.format(
            assertion=test_assertion.entity_id,
        ), {'revocation_reason': revocation_reason})
        self.assertEqual(response.status_code, 400)


class AssertionsChangedApplicationTests(SetupOAuth2ApplicationHelper, SetupIssuerHelper, BadgrTestCase):
    def test_application_can_get_changed_assertions(self):
        application_user = self.setup_user(
            authenticate=False, first_name='app', last_name='user', email='app@example.test', verified=True)
        issuer_user = self.setup_user(authenticate=False, verified=True)
        test_issuer = self.setup_issuer(owner=issuer_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        IssuerStaff.objects.create(
            issuer=test_issuer,
            role=IssuerStaff.ROLE_STAFF,
            user=application_user
        )

        application = self.setup_oauth2_application(
            user=application_user,
            allowed_scopes="rw:issuer rw:backpack rw:profile r:assertions",
            trust_email=True,
            authorization_grant_type=Application.GRANT_PASSWORD
        )

        # retrieve a token for the issuer owner user
        response = self.client.post('/o/token', data=dict(
            grant_type=application.authorization_grant_type.replace('-', '_'),
            client_id=application.client_id,
            scope="rw:issuer",
            username=issuer_user.email,
            password='secret'
        ))
        self.assertEqual(response.status_code, 200, "Can get a token for the issuer user")

        # retrieve a token for the application user
        response = self.client.post('/o/token', data=dict(
            grant_type=application.authorization_grant_type.replace('-', '_'),
            client_id=application.client_id,
            scope="rw:issuer",
            username=application_user.email,
            password='secret'
        ))
        self.assertEqual(response.status_code, 200, "Can get a token for the application user")

        test_badgeclass.issue(recipient_id='test@example.com')

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.json()['access_token'])
        response = self.client.get('/v2/assertions/changed')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)
        timestamp = response.data['timestamp']
        # Get it again to assert no new results
        response = self.client.get('/v2/assertions/changed?since={}'.format(quote_plus(timestamp)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 0)


@override_settings(
    CELERY_ALWAYS_EAGER=True
)
class AssertionWithUserTests(SetupIssuerHelper, BadgrTestCase):
    def setUp(self):
        super(AssertionWithUserTests, self).setUp()
        self.issuer = self.setup_issuer(owner=self.setup_user(email='staff@example.com'))

    def test_award_to_missing_email(self):
        email = 'idonotexistyet@example.com'
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        award = badgeclass.issue(recipient_id=email)
        self.assertEqual(award.user, None)
        recipient = self.setup_user(email=email, authenticate=False)
        award2 = BadgeInstance.objects.get(recipient_identifier=email)
        self.assertEqual(award2.user, recipient)

    def test_verification_change_owns_badge(self):
        recipient = self.setup_user(email='recipient@example.com', authenticate=False, verified=False)
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        award = badgeclass.issue(recipient_id=recipient.email)
        self.assertEqual(award.user, None)

        email = recipient.cached_emails()[0]
        email.verified = True
        email.save()
        award2 = BadgeInstance.objects.get(recipient_identifier=recipient.email)
        self.assertEqual(award2.user, recipient)

        my_id = UserRecipientIdentifier.objects.create(type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL,
                                                       identifier='http://example123.com',
                                                       user=recipient, verified=False)
        badgeclass.issue(recipient_id=my_id.identifier, recipient_type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL)
        award2 = BadgeInstance.objects.get(recipient_identifier=my_id.identifier)
        self.assertEqual(award2.user, None)
        my_id.verified = True
        my_id.save()
        award3 = BadgeInstance.objects.get(recipient_identifier=my_id.identifier)
        self.assertEqual(award3.user, recipient)

        badgeclass.issue(recipient_id='+15555555555', recipient_type=UserRecipientIdentifier.IDENTIFIER_TYPE_TELEPHONE)
        award = BadgeInstance.objects.get(recipient_identifier='+15555555555')
        self.assertEqual(award.user, None)
        my_id = UserRecipientIdentifier.objects.create(type=UserRecipientIdentifier.IDENTIFIER_TYPE_TELEPHONE,
                                                       identifier='+15555555555',
                                                       user=recipient, verified=True)
        award = BadgeInstance.objects.get(recipient_identifier=my_id.identifier)
        self.assertEqual(award.user, recipient)

    def test_verification_change_disowns_badge(self):
        recipient = self.setup_user(email='recipient@example.com', authenticate=False)
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        award = badgeclass.issue(recipient_id=recipient.email)
        self.assertEqual(award.user.pk, recipient.pk)

        my_id = UserRecipientIdentifier.objects.create(type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL,
                                                       identifier='http://example.com',
                                                       user=recipient, verified=True)
        badgeclass.issue(recipient_id='http://example.com', recipient_type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL)
        award = BadgeInstance.objects.get(recipient_identifier='http://example.com')
        self.assertEqual(award.user, recipient)
        my_id.verified = False
        my_id.save()
        award = BadgeInstance.objects.get(recipient_identifier=my_id.identifier)
        self.assertEqual(award.user, None)

        email = recipient.cached_emails()[0]
        email.verified = False
        email.save()
        award2 = badgeclass.issue(recipient_id=recipient.email)
        self.assertEqual(award2.user, None)

    def test_assertion_has_user_post_issue(self):
        recipient = self.setup_user(email='recipient@example.com', authenticate=False)
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        award = badgeclass.issue(recipient_id=recipient.email)
        self.assertEqual(award.user.pk, recipient.pk)

    def test_assertion_user_with_verification(self):
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        recipient = self.setup_user(email='recipient@example.com', authenticate=False, verified=False)
        award = badgeclass.issue(recipient_id=recipient.email)
        self.assertEqual(award.user, None)
        recipient2 = self.setup_user(email='recipient2example.com', authenticate=False)
        award2 = badgeclass.issue(recipient_id=recipient2.email)
        self.assertEqual(award2.user.pk, recipient2.pk)

    def test_assertion_user_none_post_email_or_identifier_delete(self):
        recipient = self.setup_user(email='recipient@example.com', authenticate=False)
        badgeclass = self.setup_badgeclass(issuer=self.issuer)
        badgeclass.issue(recipient_id=recipient.email)
        award = BadgeInstance.objects.get(recipient_identifier=recipient.email)
        self.assertEqual(award.user, recipient)
        CachedEmailAddress.objects.get(email='recipient@example.com').delete()
        award = BadgeInstance.objects.get(recipient_identifier=recipient.email)
        self.assertEqual(award.user, None)
        my_id = UserRecipientIdentifier.objects.create(type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL,
                                                       identifier='http://example.com',
                                                       user=recipient, verified=True)
        badgeclass.issue(recipient_id='http://example.com', recipient_type=UserRecipientIdentifier.IDENTIFIER_TYPE_URL)
        award = BadgeInstance.objects.get(recipient_identifier='http://example.com')
        self.assertEqual(award.user, recipient)
        my_id.delete()
        award = BadgeInstance.objects.get(recipient_identifier=recipient.email)
        self.assertEqual(award.user, None)


class AllowDuplicatesAPITests(SetupIssuerHelper, BadgrTestCase):
    def test_single_award_allow_duplicates(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        existing_assertion = test_badgeclass.issue('test3@example.com')

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            },
            'allowDuplicateAwards': False
        }
        response = self.client.post('/v2/badgeclasses/{}/assertions'.format(
            test_badgeclass.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 400)

        # can issue assertion with expiration
        new_assertion_props_v1 = {
            "email": 'test3@example.com',
            "create_notification": False,
            "allow_duplicate_awards": False
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), new_assertion_props_v1)
        self.assertEqual(response.status_code, 400)

        existing_assertion.revoked = True
        existing_assertion.save()
        response = self.client.post('/v2/badgeclasses/{}/assertions'.format(
            test_badgeclass.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201, "Assertion should be allowed if existing award is revoked")

    def test_single_award_allow_duplicates_against_not_expired(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(
            'test3@example.com', expires_at=timezone.now() + timezone.timedelta(days=1)
        )

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            },
            'allowDuplicateAwards': False
        }
        response = self.client.post('/v2/badgeclasses/{}/assertions'.format(
            test_badgeclass.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 400, "The badge should not award, given a unexpired existing award")

    def test_single_award_allow_duplicates_against_expired(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        test_badgeclass.issue(
            'test3@example.com', expires_at=timezone.now() - timezone.timedelta(days=1)
        )

        new_assertion_props = {
            'recipient': {
                'identity': 'test3@example.com'
            },
            'allowDuplicateAwards': False
        }
        response = self.client.post('/v2/badgeclasses/{}/assertions'.format(
            test_badgeclass.entity_id
        ), new_assertion_props, format='json')
        self.assertEqual(response.status_code, 201, "The badge should award, given an expired prior award.")

    def test_badgeclass_and_issuer_not_in_assertion_cache_record(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(
            'test3@example.com', expires_at=timezone.now() - timezone.timedelta(days=1)
        )
        _ = assertion.badgeclass  # call the foreign key attribute to ensure the related object is cached
        self.assertIsNotNone(assertion._state.fields_cache.get('badgeclass'))

        cached_assertion = BadgeInstance.cached.get(entity_id=assertion.entity_id)
        self.assertIsNone(cached_assertion._state.fields_cache.get('badgeclass'))
        self.assertIsNone(cached_assertion._state.fields_cache.get('issuer'))
