# encoding: utf-8


import base64
import json
from urllib.parse import quote_plus

from django.core.files.images import get_image_dimensions
from django.urls import reverse
from django.utils import timezone

from issuer.models import BadgeClass, IssuerStaff
from mainsite.tests import BadgrTestCase, SetupIssuerHelper
from mainsite.utils import OriginSetting


class BadgeClassTests(SetupIssuerHelper, BadgrTestCase):
    def _create_badgeclass_with_v2(self, image_path=None, **kwargs):
        if image_path is None:
            image_path = self.get_test_image_path()

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(image_path, 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Slugs',
                'description': "Recognizes slimy learners with a penchant for lettuce",
                'image': self._base64_data_uri_encode(badge_image, 'image/png'),
                'criteriaNarrative': 'Eat lettuce. Grow big.'
            }

        badgeclass_props.update(kwargs)

        response = self.client.post(
            '/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id),
            badgeclass_props, format='json'
        )
        self.assertEqual(response.status_code, 201)
        return response.data['result'][0]

    def _create_badgeclass_for_issuer_authenticated(self, image_path, **kwargs):
        with open(image_path, 'rb') as badge_image:

            image_str = self._base64_data_uri_encode(badge_image, kwargs.get("image_mimetype", "image/png"))
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': image_str,
                'criteria': 'http://wikipedia.org/Awesome',
            }
            example_badgeclass_props.update(kwargs)

            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)
            self.issuer = test_issuer
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                data=example_badgeclass_props,
                format="json"
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn('slug', response.data)
            new_badgeclass_slug = response.data.get('slug')
            BadgeClass.cached.get(entity_id=new_badgeclass_slug)

            # assert that the BadgeClass was published to and fetched from the cache
            with self.assertNumQueries(1): # the v1 badgeclass GET API now relies on a query for recipient_count
                response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badgeclass}'.format(
                    issuer=test_issuer.entity_id,
                    badgeclass=new_badgeclass_slug))
                self.assertEqual(response.status_code, 200)
                return json.loads(response.content)

    def get_test_image_base64(self, image_path=None):
        if not image_path:
            image_path = self.get_test_image_path()
        with open(image_path, 'rb') as badge_image:
            image_str = self._base64_data_uri_encode(badge_image, "image/png")
            return image_str

    def test_can_create_badgeclass(self):
        self._create_badgeclass_for_issuer_authenticated(self.get_test_image_path())

    def test_cannot_create_badgeclass_only_with_invalid_image_data_uri(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        badgeclass_props = {
            'name': 'Badge of Slugs',
            'description': "Recognizes slimy learners with a penchant for lettuce",
            'image': 'http://placekitten.com/400/400',
            'criteriaNarrative': 'Eat lettuce. Grow big.'
        }

        response = self.client.post(
            '/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id),
            badgeclass_props, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_staff_cannot_create_badgeclass(self):
        with open(self.get_test_image_path(), 'rb') as badge_image:

            image_str = self._base64_data_uri_encode(badge_image, "image/png")
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': image_str,
                'criteria': 'http://wikipedia.org/Awesome',
            }

            test_owner = self.setup_user(authenticate=False)
            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_owner)
            IssuerStaff.objects.create(issuer=test_issuer, user=test_user, role=IssuerStaff.ROLE_STAFF)
            self.issuer = test_issuer
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                data=example_badgeclass_props,
                format="json"
            )
            self.assertEqual(response.status_code, 404)

    def test_v2_post_put_badgeclasses_permissions(self):
        test_owner = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_owner)
        test_user = self.setup_user(authenticate=True, token_scope='rw:issuer')

        badgeclass_data = {
            'name': 'Test Badge',
            'description': "A testing badge",
            'image': self.get_test_image_base64(),
            'criteriaUrl': 'http://wikipedia.org/Awesome',
            'issuer': test_issuer.entity_id,
        }

        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 400)

        staff_record = IssuerStaff.objects.create(issuer=test_issuer, user=test_user, role=IssuerStaff.ROLE_STAFF)
        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 400)

        staff_record.role = IssuerStaff.ROLE_EDITOR
        staff_record.save()
        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 201)
        entity_id = response.data['result'][0]['entityId']

        badgeclass_data['name'] = 'Edited Badge'
        staff_record.role = IssuerStaff.ROLE_STAFF
        staff_record.save()
        response = self.client.put('/v2/badgeclasses/{}'.format(entity_id), data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 404)

        staff_record.role = IssuerStaff.ROLE_EDITOR
        staff_record.save()
        response = self.client.put('/v2/badgeclasses/{}'.format(entity_id), data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 200)

    def test_v2_badgeclasses_reasonable_404_error(self):
        test_owner = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_owner)
        test_user = self.setup_user(authenticate=True, token_scope='rw:issuer')

        badgeclass_data = {
            'name': 'Test Badge',
            'description': "A testing badge",
            'image': self.get_test_image_base64(),
            'criteria': 'http://wikipedia.org/Awesome',
            'issuer': 'abc123',
        }

        # Also test whether I can create a badgeclass for an issuer that does not exist.
        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_v2_badgeclasses_can_paginate(self):
        NUM_BADGE_CLASSES = 5
        PAGINATE = 2

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclasses = list(self.setup_badgeclasses(issuer=test_issuer, how_many=NUM_BADGE_CLASSES))

        test_user2 = self.setup_user(authenticate=True)
        test_issuer2 = self.setup_issuer(owner=test_user2)
        test_badgeclass2 = list(self.setup_badgeclasses(issuer=test_issuer2, how_many=NUM_BADGE_CLASSES))

        response = self.client.get('/v2/badgeclasses?num={num}'.format(num=PAGINATE))

        for badge_class in test_badgeclass2:
            for staff_record in badge_class.cached_issuer.cached_issuerstaff():
                self.assertTrue(staff_record.user_id == test_user2.id)
                self.assertTrue(staff_record.user_id != test_user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(test_badgeclass2), NUM_BADGE_CLASSES)
        self.assertEqual(len(response.data.get('result')), PAGINATE)


    def test_badgeclass_with_expires_in_days_v1(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        base_badgeclass_data = {
            'name': 'Expiring Badge',
            'description': "A testing badge that expires",
            'image': self.get_test_image_base64(),
            'criteria': 'http://wikipedia.org/Awesome',
        }

        # can create a badgeclass with valid expires_in_days
        v1_data = base_badgeclass_data.copy()
        v1_data.update(dict(
            expires=dict(
                amount=10,
                duration="days"
            ),
        ))
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges'.format(issuer=test_issuer.entity_id), data=v1_data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(response.data.get('expires'), v1_data.get('expires'))

        badgeclass_entity_id = response.data.get('slug')

        def _update_badgeclass(data):
            return self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_issuer.entity_id,
                badge=badgeclass_entity_id
            ), data=data, format="json")

        # can update a badgeclass with valid expires_in_days
        good_expires_values = [
            {"amount": 25, "duration": "days"},
            {"amount": 1000000, "duration": "weeks"},
            {"amount": 3, "duration": "months"},
            {"amount": 1, "duration": "years"},
        ]
        for good_value in good_expires_values:
            v1_data['expires'] = good_value
            response = _update_badgeclass(v1_data)
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.data.get('expires'), good_value)

        # can't use invalid expires_in_days
        bad_expires_values = [
            {"amount": 0, "duration": "days"},
            {"amount": -1, "duration": "weeks"},
            {"duration": "years"},
            {"amount": 0.5, "duration": "years"},
            {"amount": 5, "duration": "fortnights"}
        ]
        for bad_value in bad_expires_values:
            v1_data['expires'] = bad_value
            response = _update_badgeclass(v1_data)
            self.assertEqual(response.status_code, 400)

    def test_badgeclass_with_expires_in_days_v2(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        base_badgeclass_data = {
            'name': 'Expiring Badge',
            'description': "A testing badge that expires",
            'image': self.get_test_image_base64(),
            'criteriaUrl': 'http://wikipedia.org/Awesome',
            'issuer': test_issuer.entity_id,
        }

        # can create a badgeclass with valid expires_in_days
        v2_data = base_badgeclass_data.copy()
        v2_data.update(dict(
            expires=dict(
                amount=10,
                duration="days"
            )
        ))
        response = self.client.post('/v2/badgeclasses', data=v2_data, format="json")
        self.assertEqual(response.status_code, 201)
        new_badgeclass = response.data.get('result', [None])[0]
        self.assertEqual(new_badgeclass.get('expires'), v2_data.get('expires'))

        # can update a badgeclass expires_in_days
        def _update_badgeclass(data):
            return self.client.put('/v2/badgeclasses/{badge}'.format(
                badge=new_badgeclass.get('entityId')
            ), data=data, format="json")

        good_expires_values = [
            {"amount": 25, "duration": "days"},
            {"amount": 1000000, "duration": "weeks"},
            {"amount": 3, "duration": "months"},
            {"amount": 1, "duration": "years"},
        ]
        for good_data in good_expires_values:
            v2_data['expires'] = good_data
            response = _update_badgeclass(v2_data)
            self.assertEqual(response.status_code, 200)
            updated_badgeclass = response.data.get('result', [None])[0]
            self.assertDictEqual(updated_badgeclass.get('expires'), v2_data.get('expires'))

        # can't use invalid expiration
        bad_expires_values = [
            {"amount": 0, "duration": "days"},
            {"amount": -1, "duration": "weeks"},
            {"duration": "years"},
            {"amount": 0.5, "duration": "years"},
            {"amount": 5, "duration": "fortnights"}
        ]
        for bad_value in bad_expires_values:
            v2_data['expires'] = bad_value
            response = _update_badgeclass(v2_data)
            self.assertEqual(response.status_code, 400)

    def test_badgeclass_relative_expire_date_generation(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        badgeclass = BadgeClass.objects.create(issuer=test_issuer)

        badgeclass.expires_duration = BadgeClass.EXPIRES_DURATION_MONTHS
        badgeclass.expires_amount = 6

        date = badgeclass.generate_expires_at(issued_on=timezone.datetime(year=2018, month=8, day=29, hour=12, tzinfo=timezone.utc))
        self.assertEqual(date.year, 2019)
        self.assertEqual(date.month, 2)
        self.assertEqual(date.day, 28)

        badgeclass.expires_duration = BadgeClass.EXPIRES_DURATION_YEARS
        date = badgeclass.generate_expires_at(
            issued_on=timezone.datetime(year=2020, month=2, day=29, hour=12, tzinfo=timezone.utc))
        self.assertEqual(date.year, 2026)
        self.assertEqual(date.month, 2)
        self.assertEqual(date.day, 28)

        badgeclass.expires_duration = BadgeClass.EXPIRES_DURATION_DAYS
        date = badgeclass.generate_expires_at(
            issued_on=timezone.datetime(year=2020, month=2, day=29, hour=12, tzinfo=timezone.utc))
        self.assertEqual(date.year, 2020)
        self.assertEqual(date.month, 3)
        self.assertEqual(date.day, 6)

    def test_can_create_badgeclass_with_svg(self):
        self._create_badgeclass_for_issuer_authenticated(self.get_test_svg_image_path(), image_mimetype='image/svg+xml')

    def test_can_get_png_preview_for_svg_badgeclass(self):
        badgeclass_data = self._create_badgeclass_for_issuer_authenticated(self.get_test_svg_image_path(), image_mimetype='image/svg+xml')

        response = self.client.get('/public/badges/{}/image?type=png'.format(badgeclass_data.get('slug')))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response._headers.get('location')[1].endswith('.png'))

    def test_create_badgeclass_scrubs_svg(self):
        with open(self.get_testfiles_path('hacked-svg-with-embedded-script-tags.svg'), 'rb') as attack_badge_image:

            badgeclass_props = {
                'name': 'javascript SVG badge',
                'description': 'badge whose svg source attempts to execute code',
                'image': attack_badge_image,
                'criteria': 'http://svgs.should.not.be.user.input'
            }
            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id), badgeclass_props)
            self.assertEqual(response.status_code, 201)
            self.assertIn('slug', response.data)

            # make sure code was stripped
            bc = BadgeClass.objects.get(entity_id=response.data.get('slug'))
            image_content = bc.image.file.readlines()
            for ic in image_content:
                self.assertNotIn(b'onload', ic)
                self.assertNotIn(b'<script>', ic)

            # make sure we can issue the badge
            badgeinstance = bc.issue(recipient_id='fakerecipient@email.test')
            self.assertIsNotNone(badgeinstance)

    def test_when_creating_badgeclass_with_criteriatext_criteraurl_is_returned(self):
        """
        Ensure that when criteria text is submitted instead of a URL, the criteria address
        embedded in the badge is to the view that will display that criteria text
        (rather than the text itself or something...)
        """
        with open(self.get_test_image_path(), 'rb') as badge_image:
            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id), {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': badge_image,
                'criteria': 'The earner of this badge must be truly, truly awesome.',
            })
            self.assertEqual(response.status_code, 201)

            self.assertIn('slug', response.data)
            new_badgeclass_slug = response.data.get('slug')
            self.assertIn('json', response.data)
            self.assertIn('criteria', response.data.get('json'))
            expected_criterial_url = OriginSetting.HTTP + reverse('badgeclass_criteria', kwargs={
                'entity_id': new_badgeclass_slug
            })
            self.assertEqual(response.data.get('json').get('criteria'), expected_criterial_url)

    def test_cannot_create_badgeclass_without_description(self):
        """
        Ensure that the API properly rejects badgeclass creation requests that do not include a description.
        """
        with open(self.get_test_image_path(), 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Awesome',
                'image': badge_image,
                'criteria': 'The earner of this badge must be truly, truly awesome.',
            }

            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                badgeclass_props
            )
            self.assertEqual(response.status_code, 400)

    def test_cannot_create_badgeclass_if_unauthenticated(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)

        response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id))
        self.assertIn(response.status_code, (401, 403))

    def test_can_get_badgeclass_list_if_authenticated(self):
        """
        Ensure that a logged-in user can get a list of their BadgeClasses
        """
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclasses = list(self.setup_badgeclasses(issuer=test_issuer, how_many=3))

        response = self.client.get('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), len(test_badgeclasses))

    def test_cannot_get_badgeclass_list_if_unauthenticated(self):
        """
        Ensure that logged-out user can't GET the private API endpoint for badgeclass list
        """
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclasses = list(self.setup_badgeclasses(issuer=test_issuer))

        response = self.client.get('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id))
        self.assertIn(response.status_code, (401, 403))

    def test_can_delete_unissued_badgeclass(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        response = self.client.delete('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ))
        self.assertEqual(response.status_code, 204)

        self.assertFalse(BadgeClass.objects.filter(entity_id=test_badgeclass.entity_id).exists())

    def test_cannot_delete_already_issued_badgeclass(self):
        """
        A user should not be able to delete a badge class if it has been issued
        """
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        # issue badge to a recipient
        test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.delete('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ))
        self.assertEqual(response.status_code, 400)

        self.assertTrue(BadgeClass.objects.filter(entity_id=test_badgeclass.entity_id).exists())

    def test_can_delete_already_issued_badgeclass_if_all_expired(self):
        """
        A user should not be able to delete a badge class if it has been issued,
        unless all of the assertions are expired. This is a sufficient safety check.
        """
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        yesterday = timezone.now() - timezone.timedelta(days=1)
        recently = timezone.now() - timezone.timedelta(hours=12)

        # issue badge to a recipient
        test_badgeclass.issue(recipient_id='new.recipient@email.test', issued_on=yesterday, expires_at=recently)

        response = self.client.delete('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ))
        self.assertEqual(response.status_code, 204)

        self.assertFalse(BadgeClass.objects.filter(entity_id=test_badgeclass.entity_id).exists())

# TODO: Validate this is not intended behavior anymore.
# This seems not to be a requirement anymore, since in the commit message
# 344d5f5e96ad79c786fd80df6fabe92800c8826d from March '22 the validator was removed
# (and nothing else was changed). I can't validate that this is not a requirement
# anymore now though, because the commit message isn't exactly helpful
   #def test_cannot_create_badgeclass_with_invalid_markdown(self):
   #    with open(self.get_test_image_path(), 'rb') as badge_image:
   #        badgeclass_props = {
   #            'name': 'Badge of Slugs',
   #            'slug': 'badge_of_slugs_99',
   #            'description': "Recognizes slimy learners with a penchant for lettuce",
   #            'image': badge_image,
   #        }

   #        test_user = self.setup_user(authenticate=True)
   #        test_issuer = self.setup_issuer(owner=test_user)

   #        # should not create badge that has images in markdown
   #        badgeclass_props['criteria'] = 'This is invalid ![foo](image-url) markdown'
   #        response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
   #            badgeclass_props
   #        )
   #        self.assertEqual(response.status_code, 400)

    def test_can_create_badgeclass_with_valid_markdown(self):
        with open(self.get_test_image_path(), 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Slugs',
                'slug': 'badge_of_slugs_99',
                'description': "Recognizes slimy learners with a penchant for lettuce",
                'image': badge_image,
            }

            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)

            # valid markdown should be saved but html tags stripped
            badgeclass_props['criteria'] = 'This is *valid* markdown <p>mixed with raw</p> <script>document.write("and abusive html")</script>'
            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                badgeclass_props
            )
            self.assertEqual(response.status_code, 201)
            self.assertIsNotNone(response.data)
            new_badgeclass = response.data
            self.assertEqual(new_badgeclass.get('criteria_text', None), 'This is *valid* markdown mixed with raw document.write("and abusive html")')
            self.assertIn('slug', new_badgeclass)

    def test_can_create_badgeclass_with_alignment(self):
        with open(self.get_test_image_path(), 'rb') as badge_image:
            num_badgeclasses = BadgeClass.objects.count()
            test_user = self.setup_user(authenticate=True)
            test_issuer = self.setup_issuer(owner=test_user)

            badgeclass_props = {
                'name': 'Badge of Slugs',
                'description': "Recognizes slimy learners with a penchant for lettuce",
                'image': self._base64_data_uri_encode(badge_image, 'image/png'),
                'criteriaNarrative': 'Eat lettuce. Grow big.'
            }

            # valid markdown should be saved but html tags stripped
            badgeclass_props['alignments'] = [
                {
                    'targetName': 'Align1',
                    'targetUrl': 'http://examp.e.org/frmwrk/1'
                },
                {
                    'targetName': 'Align2',
                    'targetUrl': 'http://examp.e.org/frmwrk/2'
                }
            ]
            # badgeclass_props['alignment_items'] = badgeclass_props['alignments']
            response = self.client.post(
                '/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id),
                badgeclass_props, format='json'
            )
            self.assertEqual(response.status_code, 201)
            self.assertIsNotNone(response.data)
            new_badgeclass = response.data['result'][0]
            self.assertIn('alignments', list(new_badgeclass.keys()))
            self.assertEqual(len(new_badgeclass['alignments']), 2)
            self.assertEqual(
                new_badgeclass['alignments'][0]['targetName'], badgeclass_props['alignments'][0]['targetName'])

            # verify that public page renders markdown as html
            response = self.client.get('/public/badges/{}?v=2_0'.format(new_badgeclass.get('entityId')))
            self.assertIn('alignment', list(response.data.keys()))
            self.assertEqual(len(response.data['alignment']), 2)
            self.assertEqual(
                response.data['alignment'][0]['targetName'], badgeclass_props['alignments'][0]['targetName'])

            self.assertEqual(num_badgeclasses + 1, BadgeClass.objects.count())

    def test_new_badgeclass_updates_cached_issuer(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclasses(issuer=test_issuer)
        number_of_badgeclasses = len(list(test_user.cached_badgeclasses()))

        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Freshness',
                'description': "Fresh Badge",
                'image': badge_image,
                'criteria': 'http://wikipedia.org/Freshness',
            }

            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                                        example_badgeclass_props)
            self.assertEqual(response.status_code, 201)

            self.assertEqual(len(list(test_user.cached_badgeclasses())), number_of_badgeclasses + 1)

    def test_issuer_edits_reflected_in_badgeclass(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user, name='1')

        badgeclass = self.setup_badgeclass(test_issuer, name='test badgeclass 1')

        response = self.client.get('/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id))  # populate cache
        response = self.client.get('/public/badges/{}?expand=issuer'.format(badgeclass.entity_id))

        issuer_data = {
            'name': '2',
            'description': test_issuer.description,
            'email': test_user.email,
            'url': 'http://example.com'
        }
        response = self.client.put('/v2/issuers/{}'.format(test_issuer.entity_id), data=issuer_data)
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/public/badges/{}?expand=issuer'.format(badgeclass.entity_id))
        issuer_name = response.data['issuer']['name']
        self.assertEqual(issuer_name, '2')

    def test_new_badgeclass_updates_cached_user_badgeclasses(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.setup_badgeclasses(issuer=test_issuer)
        badgelist = self.client.get('/v1/issuer/all-badges')

        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Freshness',
                'description': "Fresh Badge",
                'image': badge_image,
                'criteria': 'http://wikipedia.org/Freshness',
            }

            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                example_badgeclass_props
            )
            self.assertEqual(response.status_code, 201)

        new_badgelist = self.client.get('/v1/issuer/all-badges')

        self.assertEqual(len(new_badgelist.data), len(badgelist.data) + 1)

    def _base64_data_uri_encode(self, file, mime):
        encoded = base64.b64encode(file.read()).decode()
        return "data:{};base64,{}".format(mime, encoded)

    def test_v2_badgeclass_put_image_data_uri_resized_from_450_to_400(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        with open(self.get_test_image_path(), 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': 'An awesome badge only awarded to awesome people or non-existent test entities',
                'criteriaNarrative': 'http://wikipedia.org/Awesome',
            }

            response = self.client.post(
                '/v2/issuers/{slug}/badgeclasses'.format(slug=test_issuer.entity_id),
                dict(badgeclass_props, image=badge_image),
            )
            self.assertEqual(response.status_code, 201)
            badgeclass_slug = response.data['result'][0]['entityId']

        with open(self.get_testfiles_path('450x450.png'), 'rb') as new_badge_image:
            put_response = self.client.put(
                '/v2/badgeclasses/{badge}'.format(badge=badgeclass_slug),
                dict(badgeclass_props, image=self._base64_data_uri_encode(new_badge_image, 'image/png'))
            )
            self.assertEqual(put_response.status_code, 200)

            new_badgeclass = BadgeClass.objects.get(entity_id=badgeclass_slug)
            image_width, image_height = get_image_dimensions(new_badgeclass.image.file)

            # 450x450 images should be resized to 400x400
            self.assertEqual(image_width, 400)
            self.assertEqual(image_height, 400)

    def test_v1_badgeclass_put_image_data_uri_resized_from_450_to_400(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        with open(self.get_test_image_path(), 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': 'An awesome badge only awarded to awesome people or non-existent test entities',
                'criteria': 'http://wikipedia.org/Awesome',
            }

            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                                        dict(badgeclass_props, image=badge_image),
                                        )
            self.assertEqual(response.status_code, 201)
            self.assertIn('slug', response.data)
            badgeclass_slug = response.data.get('slug')

        with open(self.get_testfiles_path('450x450.png'), 'rb') as new_badge_image:
            put_response = self.client.put(
                '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=badgeclass_slug),
                dict(badgeclass_props, image=self._base64_data_uri_encode(new_badge_image, 'image/png'))
            )
            self.assertEqual(put_response.status_code, 200)

            new_badgeclass = BadgeClass.objects.get(entity_id=badgeclass_slug)
            image_width, image_height = get_image_dimensions(new_badgeclass.image.file)

            # 450x450 images should be resized to 400x400
            self.assertEqual(image_width, 400)
            self.assertEqual(image_height, 400)

    def test_badgeclass_image_url_is_canonical(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer

        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': self._base64_data_uri_encode(badge_image, "image/png"),
                'criteriaNarrative': 'http://wikipedia.org/Awesome',
                'issuer': self.issuer.entity_id
            }

        response = self.client.post('/v2/badgeclasses', data=example_badgeclass_props, format="json")
        self.assertEqual(response.status_code, 201)
        bc = response.data['result'][0]
        self.assertIn('{}/image'.format(bc['entityId']), bc['image'])

        response = self.client.get('/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id))
        self.assertEqual(response.status_code, 200)
        bc_get = response.data['result'][0]
        self.assertIn('{}/image'.format(bc_get['entityId']), bc_get['image'])

    def test_badgeclass_put_image_data_uri(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        with open(self.get_test_image_path(), 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': 'An awesome badge only awarded to awesome people or non-existent test entities',
                'criteria': 'http://wikipedia.org/Awesome',
            }

            response = self.client.post('/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
                dict(badgeclass_props, image=badge_image),
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn('slug', response.data)
            badgeclass_slug = response.data.get('slug')

        with open(self.get_testfiles_path('400x400.png'), 'rb') as new_badge_image:
            put_response = self.client.put(
                '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=badgeclass_slug),
                dict(badgeclass_props, image=self._base64_data_uri_encode(new_badge_image, 'image/png'))
            )
            self.assertEqual(put_response.status_code, 200)

            new_badgeclass = BadgeClass.objects.get(entity_id=badgeclass_slug)
            image_width, image_height = get_image_dimensions(new_badgeclass.image.file)

            # File should be changed to new 400x400 image
            self.assertEqual(image_width, 400)
            self.assertEqual(image_height, 400)

    def test_badgeclass_put_image_non_data_uri(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        badgeclass_props = {
            'name': 'Badge of Awesome',
            'description': 'An awesome badge only awarded to awesome people or non-existent test entities',
            'criteria': 'http://wikipedia.org/Awesome',
        }

        with open(self.get_testfiles_path('300x300.png'), 'rb') as badge_image:
            post_response = self.client.post('/v1/issuer/issuers/{issuer}/badges'.format(issuer=test_issuer.entity_id),
                dict(badgeclass_props, image=badge_image),
            )
            self.assertEqual(post_response.status_code, 201)
            slug = post_response.data.get('slug')

        put_response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=slug),
            dict(badgeclass_props, image='http://example.com/example.png')
        )
        self.assertEqual(put_response.status_code, 200)

        new_badgeclass = BadgeClass.objects.get(entity_id=slug)
        image_width, image_height = get_image_dimensions(new_badgeclass.image.file)

        # File should be original 300x300 image
        self.assertEqual(image_width, 300)
        self.assertEqual(image_height, 300)

    def test_badgeclass_put_image_multipart(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        badgeclass_props = {
            'name': 'Badge of Awesome',
            'description': 'An awesome badge only awarded to awesome people or non-existent test entities',
            'criteria': 'http://wikipedia.org/Awesome',
        }

        with open(self.get_testfiles_path('300x300.png'), 'rb') as badge_image:
            post_response = self.client.post('/v1/issuer/issuers/{issuer}/badges'.format(issuer=test_issuer.entity_id),
                dict(badgeclass_props, image=badge_image),
            )
            self.assertEqual(post_response.status_code, 201)
            slug = post_response.data.get('slug')

        with open(self.get_testfiles_path('400x400.png'), 'rb') as new_badge_image:
            put_response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=slug),
                dict(badgeclass_props, image=new_badge_image),
                format='multipart'
            )
            self.assertEqual(put_response.status_code, 200)

            new_badgeclass = BadgeClass.objects.get(entity_id=slug)
            image_width, image_height = get_image_dimensions(new_badgeclass.image.file)

            # File should be changed to new 400 X 400 image
            self.assertEqual(image_width, 400)
            self.assertEqual(image_height, 400)

    def test_badgeclass_post_get_put_roundtrip(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)

        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': badge_image,
                'criteria': 'http://wikipedia.org/Awesome',
            }

            post_response = self.client.post('/v1/issuer/issuers/{issuer}/badges'.format(issuer=test_issuer.entity_id),
                example_badgeclass_props,
                format='multipart'
            )
        self.assertEqual(post_response.status_code, 201)

        self.assertIn('slug', post_response.data)
        slug = post_response.data.get('slug')
        get_response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=slug))
        self.assertEqual(get_response.status_code, 200)

        put_response = self.client.put('/v1/issuer/issuers/{issuer}/badges/{badge}'.format(issuer=test_issuer.entity_id, badge=slug),
                                       get_response.data, format='json')
        self.assertEqual(put_response.status_code, 200)

        self.assertEqual(get_response.data, put_response.data)

    def test_can_create_and_update_badgeclass_with_alignments_v1(self):
        # create a badgeclass with alignments
        alignments = [
            {
                'target_name': "Alignment the first",
                'target_url': "http://align.ment/1",
                'target_framework': None,
                'target_code': None,
                'target_description': None,
            },
            {
                'target_name': "Second Alignment",
                'target_url': "http://align.ment/2",
                'target_framework': None,
                'target_code': None,
                'target_description': None,
            },
            {
                'target_name': "Third Alignment",
                'target_url': "http://align.ment/3",
                'target_framework': None,
                'target_code': None,
                'target_description': None,
            },
        ]
        new_badgeclass = self._create_badgeclass_for_issuer_authenticated(self.get_test_image_path(), alignment=alignments)
        self.assertEqual(alignments, new_badgeclass.get('alignment', None))

        new_badgeclass_url = '/v1/issuer/issuers/{issuer}/badges/{badgeclass}'.format(
            issuer=self.issuer.entity_id,
            badgeclass=new_badgeclass['slug'])

        # update alignments -- addition and deletion
        reordered_alignments = [
            alignments[0],
            alignments[1],
            {
                'target_name': "added alignment",
                'target_url': "http://align.ment/4",
                'target_framework': None,
                'target_code': None,
                'target_description': None,
            }
        ]
        new_badgeclass['alignment'] = reordered_alignments

        response = self.client.put(new_badgeclass_url, new_badgeclass, format="json")
        updated_badgeclass = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(updated_badgeclass.get('alignment', None), reordered_alignments)

        # make sure response we got from PUT matches what we get from GET
        response = self.client.get(new_badgeclass_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, updated_badgeclass)

    def test_can_create_and_update_badgeclass_with_alignments_v2(self):
        # create a badgeclass with alignments
        alignments = [
            {
                'targetName': "Alignment the first",
                'targetUrl': "http://align.ment/1",
                'targetFramework': None,
                'targetCode': None,
                'targetDescription': None,
            },
            {
                'targetName': "Second Alignment",
                'targetUrl': "http://align.ment/2",
                'targetFramework': None,
                'targetCode': None,
                'targetDescription': None,
            },
            {
                'targetName': "Third Alignment",
                'targetUrl': "http://align.ment/3",
                'targetFramework': None,
                'targetCode': None,
                'targetDescription': None,
            },
        ]

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': self._base64_data_uri_encode(badge_image, "image/png"),
                'criteriaUrl': 'http://wikipedia.org/Awesome',
                'alignments': alignments,
                'issuer': self.issuer.entity_id
            }
            response = self.client.post('/v2/badgeclasses', data=example_badgeclass_props, format="json")
            new_badgeclass = json.loads(response.content).get('result')[0]
            self.assertEqual(alignments, new_badgeclass.get('alignments', None))

        new_badgeclass_url = '/v2/badgeclasses/{badgeclass}'.format(
            badgeclass=new_badgeclass['entityId'])

        # update alignments -- addition and deletion
        reordered_alignments = [
            alignments[0],
            alignments[1],
            {
                'targetName': "added alignment",
                'targetUrl': "http://align.ment/4",
                'targetFramework': None,
                'targetCode': None,
                'targetDescription': None,
            }
        ]
        new_badgeclass['alignments'] = reordered_alignments
        new_badgeclass['description'] = 'refreshed description'

        response = self.client.put(new_badgeclass_url, new_badgeclass, format="json")
        updated_badgeclass = json.loads(response.content).get('result')[0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(updated_badgeclass.get('alignments', None), reordered_alignments)
        self.assertEqual(updated_badgeclass.get('description', None), 'refreshed description')

        # make sure response we got from PUT matches what we get from GET
        response = self.client.get(new_badgeclass_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('result')[0], updated_badgeclass)

    def test_can_create_and_update_badgeclass_with_tags_v1(self):
        # create a badgeclass with tags
        tags = ["first", "second", "third"]
        new_badgeclass = self._create_badgeclass_for_issuer_authenticated(self.get_test_image_path(), tags=tags)
        self.assertEqual(tags, new_badgeclass.get('tags', None))

        new_badgeclass_url = '/v1/issuer/issuers/{issuer}/badges/{badgeclass}'.format(
            issuer=self.issuer.entity_id,
            badgeclass=new_badgeclass['slug']
        )

        # update tags -- addition and deletion
        reordered_tags = ["second", "third", "fourth"]
        new_badgeclass['tags'] = reordered_tags
        new_badgeclass['description'] = "new description"

        response = self.client.put(new_badgeclass_url, new_badgeclass, format="json")
        updated_badgeclass = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(updated_badgeclass.get('tags', None), reordered_tags)
        self.assertEqual(updated_badgeclass.get('description', None), "new description")

        # make sure response we got from PUT matches what we get from GET
        response = self.client.get(new_badgeclass_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, updated_badgeclass)

    def test_can_create_and_update_badgeclass_with_tags_v2(self):
        # create a badgeclass with tags
        tags = ["first", "second", "third"]

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(self.get_test_image_path(), 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': self._base64_data_uri_encode(badge_image, "image/png"),
                'criteriaUrl': 'http://wikipedia.org/Awesome',
                'issuer': self.issuer.entity_id,
                'tags': tags,
            }
            response = self.client.post('/v2/badgeclasses', data=example_badgeclass_props, format="json")
            new_badgeclass = response.data.get('result')[0]
            self.assertEqual(tags, new_badgeclass.get('tags', None))

        new_badgeclass_url = '/v2/badgeclasses/{badgeclass}'.format(
            badgeclass=new_badgeclass['entityId']
        )

        # update tags -- addition and deletion
        reordered_tags = ["second", "third", "fourth"]
        new_badgeclass['tags'] = reordered_tags

        response = self.client.put(new_badgeclass_url, new_badgeclass, format="json")
        updated_badgeclass = response.data.get('result')[0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(updated_badgeclass.get('tags', None), reordered_tags)

        # make sure response we got from PUT matches what we get from GET
        response = self.client.get(new_badgeclass_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('result')[0], updated_badgeclass)

    def test_can_create_badgeclass_with_extensions(self):
        example_extensions = {
            "extensions:originalCreator": {
                "@context": "https://openbadgespec.org/extensions/originalCreatorExtension/context.json",
                "type": ["Extension", "extensions:originalCreator"],
                "url": "https://example.org/creator-organisation.json"
            }
        }

        badgeclass = self._create_badgeclass_with_v2(extensions=example_extensions)
        self.verify_badgeclass_extensions(badgeclass, example_extensions)

    def test_can_update_badgeclass_with_extensions(self):
        example_extensions = {
            "extensions:originalCreator": {
                "@context": "https://openbadgespec.org/extensions/originalCreatorExtension/context.json",
                "type": ["Extension", "extensions:originalCreator"],
                "url": "https://example.org/creator-organisation.json"
            }
        }

        # create a badgeclass with a single extension
        badgeclass = self._create_badgeclass_with_v2(extensions=example_extensions)
        self.verify_badgeclass_extensions(badgeclass, example_extensions)

        example_extensions['extensions:ApplyLink'] = {
            "@context":"https://openbadgespec.org/extensions/applyLinkExtension/context.json",
            "type": ["Extension", "extensions:ApplyLink"],
            "url": "http://website.test/apply"
        }
        # update badgeclass and add an extension
        badgeclass['extensions'] = example_extensions
        response = self.client.put("/v2/badgeclasses/{badge}".format(badge=badgeclass.get('entityId')), data=badgeclass, format="json")
        self.assertEqual(response.status_code, 200)
        updated_badgeclass = response.data['result'][0]

        self.verify_badgeclass_extensions(updated_badgeclass, example_extensions)

    def verify_badgeclass_extensions(self, badgeclass, example_extensions):
        self.assertDictEqual(badgeclass.get('extensions'), example_extensions)

        # extensions appear when GET from api
        response = self.client.get("/v2/badgeclasses/{badge}".format(badge=badgeclass.get('entityId')))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data.get('result', [])), 0)
        fetched_badgeclass = response.data['result'][0]
        self.assertDictEqual(fetched_badgeclass.get('extensions'), example_extensions)

        # extensions appear in public object
        response = self.client.get("/public/badges/{badge}".format(badge=badgeclass.get('entityId')))
        self.assertEqual(response.status_code, 200)
        public_json = json.loads(response.content)
        for extension_name, extension_data in list(example_extensions.items()):
            self.assertDictEqual(public_json.get(extension_name), extension_data)

    def test_null_description_not_serialized(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer, description=None)
        self.assertIsNone(test_badgeclass.description)

        response = self.client.get('/v1/issuer/issuers/{issuer}/badges/{badgeclass}'.format(
            issuer=test_issuer.entity_id,
            badgeclass=test_badgeclass.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('description', None), "")

        response = self.client.get('/v2/badgeclasses/{badgeclass}'.format(
            badgeclass=test_badgeclass.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('result', [])[0].get('description', None), "")

        response = self.client.get('/public/badges/{badgeclass}'.format(
            badgeclass=test_badgeclass.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('description', None), "")

    def test_updating_issuer_cache(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user, name='Issuer 1')
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer, name='Badge 1', description='test')

        assertion_data = {
            "email": "test@example.com",
            "create_notification": False,
        }
        response = self.client.post('/v1/issuer/issuers/{issuer}/badges/{badge}/assertions'.format(
            issuer=test_issuer.entity_id,
            badge=test_badgeclass.entity_id
        ), assertion_data)
        self.assertEqual(response.status_code, 201)
        assertion_slug = response.data.get('slug')

        updated_issuer_props = {
            'name': 'Issuer 1 updated',
            'description': 'test',
            'url': 'http://example.com/',
            'email': 'example@example.org'
        }
        response = self.client.put('/v1/issuer/issuers/{}'.format(test_issuer.entity_id), updated_issuer_props)
        self.assertEqual(response.status_code, 200)

        badgeclass_props = {
            'name': 'Badge 1 updated',
            'description': 'test',
            'criteria': 'http://example.com',
        }

        response = self.client.put(
            '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_issuer.entity_id,
                badge=test_badgeclass.entity_id
            ),
            dict(badgeclass_props, image='http://example.com/example.png')
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/public/assertions/{}.json?expand=badge&expand=badge.issuer'.format(assertion_slug))
        self.assertEqual(response.data['badge']['issuer']['name'], 'Issuer 1 updated')

    def test_can_create_badgeclass_with_serverAdmin_token(self):
        issuer_owner = self.setup_user(authenticate=False)
        admin_user = self.setup_user(authenticate=True, verified=True, token_scope='rw:serverAdmin')
        test_issuer = self.setup_issuer(owner=issuer_owner)

        badgeclass_data = {
            'name': 'Test Badge',
            'description': "A testing badge",
            'image': self.get_test_image_base64(),
            'criteriaUrl': 'http://wikipedia.org/Awesome',
            'issuer': test_issuer.entity_id,
        }

        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 201)

        entity_id = response.data['result'][0]['entityId']
        badgeclass_data['name'] = 'Test Badge Version 2 Electric Badge-a-loo'
        response = self.client.put('/v2/badgeclasses/{}'.format(entity_id), data=badgeclass_data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['result'][0]['name'], badgeclass_data['name'])

    def test_create_badgeclass_without_criteria_v2_bad_request(self):
        image_path = self.get_test_image_path()
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(image_path, 'rb') as badge_image:
            badgeclass_props = {
                'name': 'Badge of Slugs',
                'description': "Recognizes slimy learners with a penchant for lettuce",
                'image': self._base64_data_uri_encode(badge_image, 'image/png')
            }
        response = self.client.post(
            '/v2/issuers/{}/badgeclasses'.format(test_issuer.entity_id),
            badgeclass_props, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["validationErrors"][0], "A criteria_url or criteria_test is required.")

    def test_create_badgeclass_without_criteria_v1_bad_request(self):
        image_path = self.get_test_image_path()
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(image_path, 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': self._base64_data_uri_encode(badge_image, 'image/png')
            }
        response = self.client.post(
            '/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
            data=example_badgeclass_props,
            format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data[0],
                         "One or both of the criteria_text and criteria_url fields must be provided")

    def test_update_badgeclass_with_null_criteria_v2_bad_request(self):
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer

        badgeclass_data = {
            'name': 'Test Badge',
            'description': "A testing badge",
            'image': self.get_test_image_base64(),
            'criteriaUrl': 'http://wikipedia.org/Awesome',
            'issuer': test_issuer.entity_id,
        }

        # Create Badge without narrative
        response = self.client.post('/v2/badgeclasses', data=badgeclass_data, format="json")
        modifyData = response.data['result'][0]
        modifyData["criteriaUrl"] = None

        # Try to remove url
        response1 = self.client.put("/v2/badgeclasses/{badge}".format(badge=modifyData.get('entityId')),
                                    data=modifyData,
                                    format="json")
        self.assertEqual(response1.status_code, 400)
        self.assertEqual(response1.data['validationErrors'][0],
                         'Changes cannot be made that would leave both criteria_url and criteria_text blank.')

        # Verify that setting one will allow removing the other.
        modifyData['criteriaNarrative'] = 'Description'
        response2 = self.client.put("/v2/badgeclasses/{badge}".format(badge=modifyData.get('entityId')),
                                    data=modifyData,
                                    format="json")
        self.assertEqual(response2.status_code, 200)

        # Try to remove narrative
        modifyData['criteriaNarrative'] = ''
        response3 = self.client.put("/v2/badgeclasses/{badge}".format(badge=modifyData.get('entityId')),
                                    data=modifyData,
                                    format="json")
        self.assertEqual(response3.status_code, 400)
        self.assertEqual(response3.data["fieldErrors"]['criteriaNarrative'][0], 'This field may not be blank.')

        # Verify that not sending either won't prevent the changes sent
        del modifyData["criteriaNarrative"]
        del modifyData["criteriaUrl"]

        response4 = self.client.put("/v2/badgeclasses/{badge}".format(badge=modifyData.get('entityId')),
                                    data=modifyData,
                                    format="json")

        self.assertEqual(response4.status_code, 200)
        returnedBadge4 = response4.data["result"][0]
        self.assertEqual(returnedBadge4.get("criteriaNarrative", None), 'Description')
        self.assertEqual(returnedBadge4.get("criteriaUrl", None), None)

    def test_update_badgeclass_with_null_criteria_v1_bad_request(self):
        image_path = self.get_test_image_path()
        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        self.issuer = test_issuer
        with open(image_path, 'rb') as badge_image:
            example_badgeclass_props = {
                'name': 'Badge of Awesome',
                'description': "An awesome badge only awarded to awesome people or non-existent test entities",
                'image': self._base64_data_uri_encode(badge_image, 'image/png'),
                'criteria': 'http://wikipedia.org/Awesome',
            }

        # Create Badge without narrative
        response = self.client.post(
            '/v1/issuer/issuers/{slug}/badges'.format(slug=test_issuer.entity_id),
            data=example_badgeclass_props,
            format="json")

        modifyData = response.data
        modifyData["criteria_url"] = None

        response1 = self.client.put(
                '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                    issuer=test_issuer.entity_id,
                    badge=modifyData['slug']
                ),
                data=modifyData,
                format="json",
        )

        self.assertEqual(response1.status_code, 400)
        self.assertEqual(response1.data[0],
                         'Changes cannot be made that would leave both criteria_url and criteria_text blank.')

        # Verify that setting one will allow removing the other.
        modifyData['criteria_text'] = 'Description'
        response2 = self.client.put(
            '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_issuer.entity_id,
                badge=modifyData['slug']
            ),
            data=modifyData,
            format="json",
        )

        self.assertEqual(response2.status_code, 200)

        # Try to remove narrative
        modifyData['criteria_text'] = ''
        response3 = self.client.put(
            '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_issuer.entity_id,
                badge=modifyData['slug']
            ),
            data=modifyData,
            format="json",
        )

        self.assertEqual(response3.status_code, 400)
        self.assertEqual(response3.data[0],
                         'Changes cannot be made that would leave both criteria_url and criteria_text blank.')

        # Verify that not sending either won't prevent the changes sent
        del modifyData["criteria_text"]
        del modifyData["criteria_url"]

        response4 = self.client.put(
            '/v1/issuer/issuers/{issuer}/badges/{badge}'.format(
                issuer=test_issuer.entity_id,
                badge=modifyData['slug']
            ),
            data=modifyData,
            format="json",
        )

        self.assertEqual(response4.status_code, 200)
        self.assertEqual(response4.data.get("criteria_text", None), 'Description')
        self.assertEqual(response4.data.get("criteria_url", None), None)


class BadgeClassesChangedApplicationTests(SetupIssuerHelper, BadgrTestCase):
    def test_application_can_get_changed_badgeclasses(self):
        issuer_user = self.setup_user(authenticate=True, verified=True, token_scope='rw:serverAdmin')
        test_issuer = self.setup_issuer(owner=issuer_user)
        test_badgeclass = self.setup_badgeclass(
            issuer=test_issuer, name='Badge Class 1', description='test')
        test_badgeclass2 = self.setup_badgeclass(
            issuer=test_issuer, name='Badge Class 2', description='test')
        test_badgeclass3 = self.setup_badgeclass(
            issuer=test_issuer, name='Badge Class 3', description='test')

        other_user = self.setup_user(authenticate=False, verified=True)
        other_issuer = self.setup_issuer(owner=other_user)

        other_badgeclass = self.setup_badgeclass(
            issuer=other_issuer, name='Badge Class 1', description='test')
        other_badgeclass2 = self.setup_badgeclass(
            issuer=other_issuer, name='Badge Class 2', description='test')
        other_badgeclass3 = self.setup_badgeclass(
            issuer=other_issuer, name='Badge Class 3', description='test')

        response = self.client.get('/v2/badgeclasses/changed')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 3)
        timestamp = response.data['timestamp']

        response = self.client.get('/v2/badgeclasses/changed?since={}'.format(quote_plus(timestamp)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 0)

        test_badgeclass.name = 'Badge Class 1 updated'
        test_badgeclass.save()

        response = self.client.get('/v2/badgeclasses/changed?since={}'.format(quote_plus(timestamp)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['result']), 1)
