# encoding: utf-8

import io
import json
import urllib.request
import urllib.parse
import urllib.error
import mock
import os
from PIL import Image
import responses

from django.core.files.base import ContentFile
from django.urls import reverse
from openbadges.verifier.openbadges_context import OPENBADGES_CONTEXT_V1_URI, OPENBADGES_CONTEXT_V2_URI, \
    OPENBADGES_CONTEXT_V2_DICT
from openbadges_bakery import unbake

from backpack.models import BackpackCollection, BackpackCollectionBadgeInstance
from backpack.tests.utils import setup_resources, setup_basic_1_0, CURRENT_DIRECTORY
from badgeuser.models import CachedEmailAddress
from issuer.models import BadgeClass, BadgeInstance, Issuer
from issuer.utils import OBI_VERSION_CONTEXT_IRIS, UNVERSIONED_BAKED_VERSION
from mainsite.models import BadgrApp
from mainsite.tests import BadgrTestCase, Ob2Generators, SetupIssuerHelper
from mainsite.utils import OriginSetting


class PublicAPITests(SetupIssuerHelper, BadgrTestCase):
    """
    Tests the ability of an anonymous user to GET one public badge object
    """

    def test_get_issuer_object(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)

        with self.assertNumQueries(0):
            response = self.client.get('/public/issuers/{}'.format(test_issuer.entity_id))
            self.assertEqual(response.status_code, 200)

    def test_get_issuer_object_that_doesnt_exist(self):
        fake_entity_id = 'imaginary-issuer'
        with self.assertRaises(Issuer.DoesNotExist):
            Issuer.objects.get(entity_id=fake_entity_id)

        # a db miss will generate 2 queries, lookup by entity_id and lookup by slug
        with self.assertNumQueries(2):
            response = self.client.get('/public/issuers/imaginary-issuer')
            self.assertEqual(response.status_code, 404)

    def test_get_badgeclass_image_with_redirect(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        with self.assertNumQueries(0):
            response = self.client.get('/public/badges/{}/image'.format(test_badgeclass.entity_id))
            self.assertEqual(response.status_code, 302)

    def test_get_badgeclass_image_wide(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        # Get badgeclass public page as a bot
        headers = {'HTTP_USER_AGENT': 'Twitterbot/1.0'}
        response = self.client.get('/public/badges/{}'.format(test_badgeclass.entity_id), **headers)
        # should have received an html stub with og meta tags
        self.assertTrue(response.get('content-type').startswith('text/html'))
        self.assertContains(response, 'fmt=wide')  # ensure the image is linked properly with the wide format

        with self.assertNumQueries(0):
            response = self.client.get('/public/badges/{}/image?type=png&fmt=wide'.format(test_badgeclass.entity_id))
            self.assertEqual(response.status_code, 302)

        response = self.client.get(response.url)  # Get the actual image URL from media storage
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get('content-type').startswith('image/png'))
        imagefile = ContentFile(b''.join(response.streaming_content))
        image = Image.open(imagefile)
        self.assertEqual(image.width, 764)
        self.assertEqual(image.height, 400)

    def test_get_assertion_image_with_redirect(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        with self.assertNumQueries(0):
            response = self.client.get('/public/assertions/{}/image'.format(assertion.entity_id), follow=False)
            self.assertEqual(response.status_code, 302)

    def test_get_assertion_json_explicit(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        with self.assertNumQueries(1):
            response = self.client.get('/public/assertions/{}'.format(assertion.entity_id),
                                       **{'HTTP_ACCEPT': 'application/json'})
            self.assertEqual(response.status_code, 200)

            # Will raise error if response is not JSON.
            content = json.loads(response.content)

            self.assertEqual(content['type'], 'Assertion')

    def test_get_assertion_json_implicit(self):
        """ Make sure we serve JSON by default if there is a missing Accept header. """
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        with self.assertNumQueries(1):
            response = self.client.get('/public/assertions/{}'.format(assertion.entity_id))
            self.assertEqual(response.status_code, 200)

            # Will raise error if response is not JSON.
            content = json.loads(response.content)

            self.assertEqual(content['type'], 'Assertion')

    def test_get_for_revoked_assertion_and_deleted_badge_class_returns_404(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.get('/public/assertions/{}?action=download'.format(assertion.entity_id))
        self.assertEqual(response.status_code, 200)

        assertion.revoked = True
        assertion.revocation_reason = 'For testing'
        assertion.save()

        response2 = self.client.get('/public/assertions/{}?action=download'.format(assertion.entity_id))
        self.assertEqual(response2.status_code, 200)

        test_badgeclass.delete()
        response3 = self.client.get('/public/assertions/{}?action=download'.format(assertion.entity_id))
        self.assertEqual(response3.status_code, 404)

    def test_scrapers_get_html_stub(self):
        test_user_email = 'test.user@email.test'

        test_user = self.setup_user(authenticate=False, email=test_user_email)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id=test_user_email)
        assertion.pending  # prepopulate cache

        # create a shared collection
        test_collection = BackpackCollection.objects.create(
            created_by=test_user, name='Test Collection', description="testing")
        BackpackCollectionBadgeInstance.objects.create(
            collection=test_collection, badgeinstance=assertion, badgeuser=test_user)  # add assertion to collection
        test_collection.published = True
        test_collection.save()
        self.assertIsNotNone(test_collection.share_url)

        testcase_headers = [
            # bots/scrapers should get an html stub with opengraph tags
            {'HTTP_USER_AGENT':
                'LinkedInBot/1.0 (compatible; Mozilla/5.0; Jakarta Commons-HttpClient/3.1 +http://www.linkedin.com)'},
            {'HTTP_USER_AGENT': 'Twitterbot/1.0'},
            {'HTTP_USER_AGENT': 'facebook'},
            {'HTTP_USER_AGENT': 'Facebot'},
            {'HTTP_USER_AGENT': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'},
        ]

        # check that public assertion pages get og stubs served to bots
        for headers in testcase_headers:
            with self.assertNumQueries(0):
                response = self.client.get('/public/assertions/{}'.format(assertion.entity_id), **headers)
                self.assertEqual(response.status_code, 200)

                # should have received an html stub with og meta tags
                self.assertTrue(response.get('content-type').startswith('text/html'))
                self.assertContains(response, '<meta property="og:url" content="{}">'.format(
                    assertion.public_url), html=True)
                png_image_url = "{}{}?type=png".format(
                    OriginSetting.HTTP,
                    reverse('badgeclass_image', kwargs={'entity_id': assertion.cached_badgeclass.entity_id})
                )
                self.assertContains(response, '<meta property="og:image" content="{}'.format(png_image_url))

        # check that collections get og stubs served to bots
        for headers in testcase_headers:
            with self.assertNumQueries(0):
                response = self.client.get(test_collection.share_url, **headers)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get('content-type').startswith('text/html'))
                self.assertContains(response, '<meta property="og:url" content="{}">'.format(
                    test_collection.share_url), html=True)

    def test_scraping_empty_backpack_share_returns_html_with_no_image_based_tags(self):
        test_user_email = 'test.user@email.test'
        test_user = self.setup_user(authenticate=False, email=test_user_email)
        # empty backpack
        test_collection = BackpackCollection.objects.create(
            created_by=test_user, name='Test Collection', description="testing")
        test_collection.published = True
        test_collection.save()

        testcase_headers = [
            # bots/scrapers should get an html stub with opengraph tags
            {'HTTP_USER_AGENT':
                'LinkedInBot/1.0 (compatible; Mozilla/5.0; Jakarta Commons-HttpClient/3.1 +http://www.linkedin.com)'},
            {'HTTP_USER_AGENT': 'Twitterbot/1.0'},
            {'HTTP_USER_AGENT': 'facebook'},
            {'HTTP_USER_AGENT': 'Facebot'},
            {'HTTP_USER_AGENT': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'},
        ]

        for headers in testcase_headers:
            with self.assertNumQueries(0):
                response = self.client.get(test_collection.share_url, **headers)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'og:image', html=True)
                self.assertNotContains(response, '<img src="">', html=True)

    def test_public_collection_json(self):
        test_user_email = 'test.user@email.test'

        test_user = self.setup_user(authenticate=False, email=test_user_email)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id=test_user_email)
        assertion.pending  # prepopulate cache

        # create a shared collection
        test_collection = BackpackCollection.objects.create(created_by=test_user, name='Test Collection',
                                                            description="testing")
        BackpackCollectionBadgeInstance.objects.create(collection=test_collection, badgeinstance=assertion,
                                                       badgeuser=test_user)  # add assertion to collection
        test_collection.published = True
        test_collection.save()
        self.assertIsNotNone(test_collection.share_url)

        response = self.client.get(
            '/public/collections/{}'.format(test_collection.share_hash), header={'Accept': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['entityId'], test_collection.entity_id)

    def test_get_assertion_html_redirects_to_frontend(self):
        badgr_app = BadgrApp(
            cors='frontend.ui', is_default=True, signup_redirect='http://frontend.ui/signup',
            public_pages_redirect='http://frontend.ui/public'
        )
        badgr_app.save()

        badgr_app_two = BadgrApp(cors='stuff.com', is_default=False,
                                 signup_redirect='http://stuff.com/signup',
                                 public_pages_redirect='http://stuff.com/public')
        badgr_app_two.save()

        redirect_accepts = [
            {'HTTP_ACCEPT': ('application/xml,application/xhtml+xml,text/html;q=0.9, '
                'text/plain;q=0.8,image/png,*/*;q=0.5')},  # safari/chrome
            {'HTTP_ACCEPT': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                '*/*;q=0.8')},  # firefox
            {'HTTP_ACCEPT': 'text/html, application/xhtml+xml, image/jxr, */*'},  # edge
        ]
        json_accepts = [
            {'HTTP_ACCEPT': '*/*'},  # curl
            {},  # no accept header
        ]

        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_issuer.badgrapp = badgr_app_two
        test_issuer.save()
        test_issuer.cached_badgrapp  # publish badgrapp to cache
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        for headers in redirect_accepts:
            with self.assertNumQueries(1):
                response = self.client.get('/public/assertions/{}'.format(assertion.entity_id), **headers)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.get('Location'),
                                 'http://stuff.com/public/assertions/{}'.format(assertion.entity_id))

        for headers in json_accepts:
            with self.assertNumQueries(1):
                response = self.client.get('/public/assertions/{}'.format(assertion.entity_id), **headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get('Content-Type'), "application/ld+json")

    @responses.activate
    def test_uploaded_badge_returns_coerced_json(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        with mock.patch('mainsite.blacklist.api_query_is_in_blacklist',
                        new=lambda a, b: False):
            response = self.client.post(
                '/v1/earner/badges', post_input
            )
        self.assertEqual(response.status_code, 201)
        uploaded_badge = response.data
        assertion_entityid = uploaded_badge.get('id')
        assertion_url = '/public/assertions/{}?v=2_0'.format(assertion_entityid)
        response = self.client.get(assertion_url)
        self.assertEqual(response.status_code, 200)
        coerced_assertion = response.data
        assertion = BadgeInstance.objects.get(entity_id=assertion_entityid)
        self.assertDictEqual(coerced_assertion, assertion.get_json(obi_version="2_0"))
        # We should not change the declared jsonld ID of the requested object
        self.assertEqual(coerced_assertion.get('id'), 'http://a.com/instance')

    def verify_baked_image_response(self, assertion, response, obi_version, **kwargs):
        self.assertEqual(response.status_code, 200)
        baked_image = io.BytesIO(b"".join(response.streaming_content))
        baked_json = unbake(baked_image)
        baked_metadata = json.loads(baked_json)
        assertion_metadata = assertion.get_json(obi_version=obi_version, **kwargs)
        self.assertDictEqual(baked_metadata, assertion_metadata)

    def test_get_versioned_baked_images(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.get('/public/assertions/{}/image'.format(assertion.entity_id), follow=True)
        self.verify_baked_image_response(assertion, response, obi_version=UNVERSIONED_BAKED_VERSION)

        for obi_version in list(OBI_VERSION_CONTEXT_IRIS.keys()):
            response = self.client.get('/public/assertions/{assertion}/baked?v={version}'.format(
                assertion=assertion.entity_id,
                version=obi_version
            ), follow=True)

            if obi_version == UNVERSIONED_BAKED_VERSION:
                # current_obi_versions aren't re-baked expanded
                self.verify_baked_image_response(assertion, response, obi_version=obi_version)
            else:
                self.verify_baked_image_response(
                    assertion,
                    response,
                    obi_version=obi_version,
                    expand_badgeclass=True,
                    expand_issuer=True,
                    include_extra=True
                )

    def test_cache_updated_on_issuer_update(self):
        original_badgeclass_name = 'Original Badgeclass Name'
        new_badgeclass_name = 'new badgeclass name'

        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer, name=original_badgeclass_name)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.get(
            '/public/assertions/{}?expand=badge'.format(assertion.entity_id), Accept='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('badge', {}).get('name', None), original_badgeclass_name)

        test_badgeclass.name = new_badgeclass_name
        test_badgeclass.save()

        response = self.client.get(
            '/public/assertions/{}?expand=badge'.format(assertion.entity_id), Accept='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('badge', {}).get('name', None), new_badgeclass_name)


class PendingAssertionsPublicAPITests(SetupIssuerHelper, BadgrTestCase):
    @responses.activate
    def test_pending_assertion_returns_404(self):
        setup_resources([
            {'url': 'http://a.com/assertion-embedded1', 'filename': '2_0_assertion_embedded_badgeclass.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': 'http://a.com/badgeclass_image', 'filename': "unbaked_image.png", 'mode': 'rb'},
        ])
        unverified_email = 'test@example.com'
        test_user = self.setup_user(email='verified@example.com', authenticate=True)
        CachedEmailAddress.objects.add_email(test_user, unverified_email)
        post_input = {"url": "http://a.com/assertion-embedded1"}

        with mock.patch('mainsite.blacklist.api_query_is_in_blacklist',
                        new=lambda a, b: False):
            self.client.post('/v2/backpack/import', post_input,
                    format='json')
        assertion = BadgeInstance.objects.first()

        self.client.logout()
        get_resp = self.client.get('/public/assertions/{}'.format(assertion.entity_id))
        self.assertEqual(get_resp.status_code, 404)


class OEmbedTests(SetupIssuerHelper, BadgrTestCase):
    """
    oEmbed url schemes:
      - {HTTP_ORIGIN}/public/assertions/{entity_id}/embed

    oEmbed API endpoint:
      - {HTTP_ORIGIN}/public/oembed?format=json&url={HTTP_ORIGIN}/public/assertions/{entity_id}


    """

    def test_get_oembed_json(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        # with self.assertNumQueries(0):
        response = self.client.get('/public/oembed?format=json&url={}'.format(urllib.parse.quote(assertion.jsonld_id)))
        self.assertEqual(response.status_code, 200)

    def test_endpoint_handles_malformed_urls(self):
        response = self.client.get('/public/oembed?format=json&url={}'.format(urllib.parse.quote('ralph the dog')))
        self.assertEqual(response.status_code, 404)

    def test_auto_discovery_of_api_endpoint(self):
        test_user = self.setup_user(authenticate=False)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)
        assertion = test_badgeclass.issue(recipient_id='new.recipient@email.test')

        response = self.client.get(
            '/public/assertions/{}'.format(assertion.entity_id),
            HTTP_USER_AGENT='Mozilla/5.0 (compatible; Embedly/0.2; +http://support.embed.ly/)',
            HTTP_ACCEPT='text/html,application/xml,application/xhtml+xml;q=0.9,text//plain;q0.8,image/png,*/*;q=0.5'

        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'oembed')


class PublicReverificationTests(SetupIssuerHelper, BadgrTestCase, Ob2Generators):

    @responses.activate
    @mock.patch('issuer.public_api.openbadges.verify')
    def test_can_reverify_basic(self, mock_verify):
        issuer_ob2 = self.generate_issuer_obo2()
        badgeclass_ob2 = self.generate_badgeclass_ob2()
        assertion_ob2 = self.generate_assertion_ob2(source_url='https://example.com/assertion/1')

        responses.add(responses.GET,
                      badgeclass_ob2['image'],
                      body=open(os.path.join(CURRENT_DIRECTORY, 'testfiles/unbaked_image.png'), 'rb').read(),
                      status=200, content_type='image/png')

        issuer_image = Issuer.objects.image_from_ob2(issuer_ob2)
        badgeclass_image = BadgeClass.objects.image_from_ob2(badgeclass_ob2)
        badgeinstance_image = BadgeInstance.objects.image_from_ob2(badgeclass_image, assertion_ob2)

        issuer, _ = Issuer.objects.get_or_create_from_ob2(issuer_ob2, image=issuer_image)
        badgeclass, _ = BadgeClass.objects.get_or_create_from_ob2(issuer, badgeclass_ob2, image=badgeclass_image)

        revocation_reason = "Manually revoked by Issuer"

        with mock.patch('mainsite.blacklist.api_query_is_in_blacklist', new=lambda a, b: False):
            assertion, _ = BadgeInstance.objects.get_or_create_from_ob2(
                badgeclass,
                assertion_ob2,
                recipient_identifier='test@example.com',
                image=badgeinstance_image
            )

            mock_verify.return_value = {
                'report': self.generate_ob2_report(validationSubject=assertion_ob2['id']),
                'graph': [assertion_ob2, badgeclass_ob2, issuer_ob2],
                'input': self.generate_ob2_input(input_type='url', value=assertion_ob2['id'])
            }

            # openbadges.verify response (Not Revoked)
            verify_response = self.client.post('/public/verify', data={'entity_id': assertion.entity_id})
            self.assertFalse('revoked' in verify_response.data['result'][0])
            self.assertFalse('revocationReason' in verify_response.data['result'][0])
            # badge instance is not revoked
            self.assertFalse(BadgeInstance.objects.last().revoked)

            # openbadges.verify response (Revoked)
            mock_verify.return_value = {
                'graph': [
                    {**assertion_ob2, "revocationReason": revocation_reason,
                        "revoked": True}, badgeclass_ob2, issuer_ob2
                ]
            }

            # call badge check with this assertion (revoked)
            revoked_response = self.client.post('/public/verify', data={'entity_id': assertion.entity_id})
            # response contains revocation flag and revocation reason
            self.assertTrue(revoked_response.data['result'][0]['revoked'])
            self.assertEqual(revoked_response.data['result'][0]['revocationReason'], revocation_reason)
            # badge instance is revoked, revocation_reason has not changed
            self.assertTrue(BadgeInstance.objects.last().revoked)
            self.assertEqual(BadgeInstance.objects.last().revocation_reason, revocation_reason)

            # attempt to revalidate a revoked badge.
            second_revoked_response = self.client.post('/public/verify', data={'entity_id': assertion.entity_id})
            # still revoked
            self.assertTrue(second_revoked_response.data['result'][0]['revoked'])
            # returns original revoked response
            self.assertEqual(second_revoked_response.data['result'][0]['revocationReason'], revocation_reason)
            # badge instance is revoked, revocation_reason has not changed
            self.assertTrue(BadgeInstance.objects.last().revoked)
            self.assertEqual(BadgeInstance.objects.last().revocation_reason, revocation_reason)

            # attempting to revalidate a revoked badge with a new revocation reason does not update the original reason.
            mock_verify.return_value["graph"][0].update(
                {'revocationReason': 'New reason should not replace original reason'})
            third_revoked_response = self.client.post('/public/verify', data={'entity_id': assertion.entity_id})
            # still revoked
            self.assertTrue(third_revoked_response.data['result'][0]['revoked'])
            # returns original revoked response, revocation_reason has not changed
            self.assertEqual(third_revoked_response.data['result'][0]['revocationReason'], revocation_reason)
            # badge instance is revoked, revocation_reason has not changed
            self.assertTrue(BadgeInstance.objects.last().revoked)
            self.assertEqual(BadgeInstance.objects.last().revocation_reason, revocation_reason)
