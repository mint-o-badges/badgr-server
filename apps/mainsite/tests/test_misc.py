import hashlib
from hashlib import sha256
import mock
from PIL import Image
from operator import attrgetter
import os
import pytz
import re
import responses
import shutil
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse
import warnings

from django.conf import settings
from django.core import mail
from django.core.cache import cache, CacheKeyWarning
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import override_settings, TransactionTestCase
from django.utils import timezone

from rest_framework import serializers
from rest_framework.exceptions import UnsupportedMediaType
from oauth2_provider.models import AccessToken, Application

from badgeuser.models import BadgeUser, CachedEmailAddress
from issuer.models import BadgeClass, Issuer, BadgeInstance
from mainsite.models import BadgrApp, AccessTokenProxy, AccessTokenScope
from mainsite import TOP_DIR, blacklist
from mainsite.serializers import DateTimeWithUtcZAtEndField
from mainsite.tests import SetupIssuerHelper
from mainsite.tests.base import BadgrTestCase
from mainsite.utils import fetch_remote_file_to_storage, verify_svg


class TestDateSerialization(BadgrTestCase):
    class TestSerializer(serializers.Serializer):
        the_date = DateTimeWithUtcZAtEndField(source="date_field")

    class TestHolder(object):
        date_field = None

        def __init__(self, date_field):
            self.date_field = date_field

    def test_date_serialization(self):
        utc_date = self.TestHolder(timezone.datetime(2019, 12, 6, 12, 0, tzinfo=pytz.utc))
        la_date = self.TestHolder(pytz.timezone(
            'America/Los_Angeles').localize(timezone.datetime(2019, 12, 6, 12, 0)))  # -8 hours
        ny_date = self.TestHolder(pytz.timezone(
            'America/New_York').localize(timezone.datetime(2019, 12, 6, 12, 0)))  # -5 hours

        utc_serializer = self.TestSerializer(utc_date)
        la_serializer = self.TestSerializer(la_date)
        ny_serializer = self.TestSerializer(ny_date)

        self.assertEqual(utc_serializer.data['the_date'], '2019-12-06T12:00:00Z')
        self.assertEqual(la_serializer.data['the_date'], '2019-12-06T20:00:00Z')
        self.assertEqual(ny_serializer.data['the_date'], '2019-12-06T17:00:00Z')


class TestTokenDenorm(BadgrTestCase, SetupIssuerHelper):
    def test_scopes_created(self):
        self.setup_user(email="foo@bar.com", authenticate=True, token_scope="rw:backpack r:profile")
        self.assertEqual(2, AccessTokenScope.objects.all().count())

    def test_library_access_token_scope_denormalization(self):
        # Creating an AccessToken (library model) results in correct scopes
        scope_string = 'foo bar'
        scopes = sorted(scope_string.split(' '))
        app = Application.objects.create(client_id="app", client_type="public", authorization_grant_type="implicit",)
        token = AccessToken.objects.create(
            application=app,
            scope=scope_string,
            expires=timezone.now() + timezone.timedelta(hours=1))
        qs = AccessTokenScope.objects.filter(token=token).order_by('scope')
        self.assertQuerysetEqual(qs, scopes, attrgetter('scope'))

    def test_access_token_proxy_scope_denormalization(self):
        # Creating an AccessTokenProxy (our model) results in correct scopes
        scope_string = 'badgr is great'
        scopes = sorted(scope_string.split(' '))
        app = Application.objects.create(client_id="app", client_type="public", authorization_grant_type="implicit", )
        proxy_token = AccessTokenProxy.objects.create(
            application=app,
            scope=scope_string,
            expires=timezone.now() + timezone.timedelta(hours=1))
        qs = AccessTokenScope.objects.filter(token=proxy_token).order_by('scope')
        self.assertQuerysetEqual(qs, scopes, attrgetter('scope'))


class TestCacheSettings(TransactionTestCase):

    def test_long_cache_keys_shortened(self):
        cache_settings = {
            'default': {
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': os.path.join(TOP_DIR, 'test.cache'),
            }
        }
        long_key_string = "X" * 251

        with override_settings(CACHES=cache_settings):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # memcached limits key length to 250
                cache.set(long_key_string, "hello cached world")

                self.assertEqual(len(w), 1)
                self.assertIsInstance(w[0].message, CacheKeyWarning)

        # Activate optional cache key length checker
        cache_settings['default']['KEY_FUNCTION'] = 'mainsite.utils.filter_cache_key'

        with override_settings(CACHES=cache_settings):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # memcached limits key length to 250
                cache.set(long_key_string, "hello cached world")

                self.assertEqual(len(w), 0)

                retrieved = cache.get(long_key_string)

                self.assertEqual(retrieved, "hello cached world")


class TestUtils(BadgrTestCase, SetupIssuerHelper):
    def test_svg_verify(self):
        with open(self.get_test_svg_image_path(), 'rb') as svg_badge_image:
            self.assertTrue(verify_svg(svg_badge_image))


@override_settings(
    HTTP_ORIGIN='http://api.testserver',
    ACCOUNT_EMAIL_CONFIRMATION_HMAC=True
)
class TestSignup(BadgrTestCase):
    def test_user_signup_email_confirmation_redirect(self):
        from django.conf import settings
        http_origin = getattr(settings, 'HTTP_ORIGIN')
        badgr_app = BadgrApp(
            cors='frontend.ui',
            email_confirmation_redirect='http://frontend.ui/login/',
            forgot_password_redirect='http://frontend.ui/forgot-password/',
            is_default=True
        )
        badgr_app.save()

        post_data = {
            'first_name': 'Tester',
            'last_name': 'McSteve',
            'email': 'test12345@example.com',
            'password': 'secr3t4nds3cur3'
        }
        response = self.client.post('/v1/user/profile', post_data)
        self.assertEqual(response.status_code, 201)

        user = BadgeUser.objects.get(entity_id=response.data.get('slug'))

        self.assertEqual(len(mail.outbox), 1)
        url_match = re.search(r'{}(/v1/user/confirmemail.*)'.format(http_origin), mail.outbox[0].body)
        self.assertIsNotNone(url_match)
        confirm_url = url_match.group(1)

        expected_redirect_url = '{badgrapp_redirect}{first_name}?authToken={auth}&email={email}'.format(
            badgrapp_redirect=badgr_app.email_confirmation_redirect,
            first_name=post_data['first_name'],
            email=urllib.parse.quote(post_data['email']),
            auth=user.auth_token
        )

        response = self.client.get(confirm_url, follow=False)
        self.assertEqual(response.status_code, 302)

        actual = urllib.parse.urlparse(response.get('location'))
        expected = urllib.parse.urlparse(expected_redirect_url)
        self.assertEqual(actual.netloc, expected.netloc)
        self.assertEqual(actual.scheme, expected.scheme)

        actual_query = urllib.parse.parse_qs(actual.query)
        expected_query = urllib.parse.parse_qs(expected.query)
        self.assertEqual(actual_query.get('email'), expected_query.get('email'))
        self.assertIsNotNone(actual_query.get('authToken'))


@override_settings(
    ACCOUNT_EMAIL_CONFIRMATION_HMAC=False
)
class TestEmailCleanupCommand(BadgrTestCase):
    def test_email_added_for_user_missing_one(self):
        user = BadgeUser(email="newtest@example.com", first_name="Test", last_name="User")
        user.save()
        self.assertFalse(CachedEmailAddress.objects.filter(user=user).exists())

        user2 = BadgeUser(email="newtest2@example.com", first_name="Test2", last_name="User")
        user2.save()
        email2 = CachedEmailAddress(user=user2, email="newtest2@example.com", verified=False, primary=True)
        email2.save()

        call_command('clean_email_records')

        email_record = CachedEmailAddress.objects.get(user=user)
        self.assertFalse(email_record.verified)
        self.assertTrue(email_record.emailconfirmation_set.exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_unverified_unprimary_email_sends_confirmation(self):
        """
        If there is only one email, and it's not primary, set it as primary.
        If it's not verified, send a verification.
        """
        user = BadgeUser(email="newtest@example.com", first_name="Test", last_name="User")
        user.save()
        email = CachedEmailAddress(email=user.email, user=user, verified=False, primary=False)
        email.save()

        user2 = BadgeUser(email="newtest@example.com", first_name="Error", last_name="User")
        user2.save()

        self.assertEqual(BadgeUser.objects.count(), 2)

        call_command('clean_email_records')

        email_record = CachedEmailAddress.objects.get(user=user)
        self.assertTrue(email_record.primary)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(BadgeUser.objects.count(), 1)


class TestBlacklist(BadgrTestCase):
    def setUp(self):
        super(TestBlacklist, self).setUp()
        self.user, _ = BadgeUser.objects.get_or_create(email='test@example.com')
        self.cached_email, _ = CachedEmailAddress.objects.get_or_create(
            user=self.user, email='test@example.com', verified=True, primary=True)
        self.issuer = Issuer.objects.create(
            name="Open Badges",
            created_at="2015-12-15T15:55:51Z",
            created_by=None,
            slug="open-badges",
            source_url="http://badger.openbadges.org/program/meta/bda68a0b505bc0c7cf21bc7900280ee74845f693",
            source="test-fixture",
            image=""
        )

        self.badge_class = BadgeClass.objects.create(
            name="MozFest Reveler",
            created_at="2015-12-15T15:55:51Z",
            created_by=None,
            slug="mozfest-reveler",
            criteria_text=None,
            source_url="http://badger.openbadges.org/badge/meta/mozfest-reveler",
            source="test-fixture",
            image="",
            issuer=self.issuer
        )

    Inputs = [('email', 'test@example.com'),
              ('url', 'http://example.com'),
              ('telephone', '+16175551212'),
              ]

    @override_settings(
        BADGR_BLACKLIST_API_KEY='123',
        BADGR_BLACKLIST_QUERY_ENDPOINT='http://example.com',
    )
    @responses.activate
    def test_blacklist_api_query_is_in_blacklist(self):
        id_type, id_value = self.Inputs[0]

        responses.add(
            responses.GET, 'http://example.com?id=' + blacklist.generate_hash(id_type, id_value),
            body="{\"msg\": \"ok\"}", status=200
        )

        in_blacklist = blacklist.api_query_is_in_blacklist(id_type, id_value)
        self.assertTrue(in_blacklist)

    @override_settings(
        BADGR_BLACKLIST_API_KEY='123',
        BADGR_BLACKLIST_QUERY_ENDPOINT='http://example.com',
    )
    @responses.activate
    def test_blacklist_assertion_to_recipient_in_blacklist(self):
        id_type, id_value = self.Inputs[0]
        with mock.patch('mainsite.blacklist.api_query_is_in_blacklist', new=lambda a, b: True):
            with self.assertRaises(ValidationError):
                BadgeInstance.objects.create(
                    recipient_identifier="test@example.com",
                    badgeclass=self.badge_class,
                    issuer=self.issuer,
                    image="uploads/badges/local_badgeinstance_174e70bf-b7a8-4b71-8125-c34d1a994a7c.png",
                    acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
                )
        self.assertIsNone(BadgeInstance.objects.first())

    @override_settings(
        BADGR_BLACKLIST_API_KEY='123',
        BADGR_BLACKLIST_QUERY_ENDPOINT='http://example.com',
    )
    @responses.activate
    def test_blacklist_api_query_is_in_blacklist_false(self):
        id_type, id_value = self.Inputs[1]

        responses.add(
            responses.GET, 'http://example.com?id=' + blacklist.generate_hash(id_type, id_value),
            body="{\"msg\": \"no\"}", status=404
        )

        in_blacklist = blacklist.api_query_is_in_blacklist(id_type, id_value)
        self.assertFalse(in_blacklist)

    @override_settings(
        BADGR_BLACKLIST_API_KEY='123',
        BADGR_BLACKLIST_QUERY_ENDPOINT='http://example.com',
    )
    def test_blacklist_not_configured_throws_exception(self):
        id_type, id_value = self.Inputs[1]
        with mock.patch('mainsite.blacklist.api_query_recipient_id', new=lambda a, b, c, d: None):
            with self.assertRaises(Exception):
                blacklist.api_query_is_in_blacklist(id_type, id_value)

    @override_settings(
        BADGR_BLACKLIST_API_KEY='123',
        BADGR_BLACKLIST_QUERY_ENDPOINT='http://example.com',
    )
    def test_blacklistgenerate_hash(self):
        # The generate_hash function implementation should not change; We risk contacting people on the blacklist
        for (id_type, id_value) in self.Inputs:
            got = blacklist.generate_hash(id_type, id_value)
            expected = "{id_type}$sha256${hash}".format(
                id_type=id_type, hash=sha256(id_value.encode('utf-8')).hexdigest())
            self.assertEqual(got, expected)


class TestRemoteFileToStorage(SetupIssuerHelper, BadgrTestCase):
    mime_types = ['image/png', 'image/svg+xml', 'image/jpeg']
    test_uploaded_path = os.path.join('testfiles')
    path_to_mediafiles = getattr(settings, 'MEDIA_ROOT')
    test_url = 'http://example.com/123abc'

    def tearDown(self):
        dir = os.path.join('{base_url}/{upload_to}/cached/'.format(
            base_url=default_storage.location,
            upload_to=self.test_uploaded_path
        ))

        try:
            shutil.rmtree(dir)
        except OSError as e:
            print(("%s does not exist and was not deleted" % 'me'))

    def mimic_hashed_file_name(self, name, ext=''):
        return hashlib.md5(name.encode('utf-8')).hexdigest() + ext

    @responses.activate
    def test_remote_url_is_data_uri(self):
        data_uri_as_url = open(self.get_test_image_data_uri()).read()
        status_code, storage_name = fetch_remote_file_to_storage(
            data_uri_as_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertEqual(status_code, 200)

    @responses.activate
    def test_svg_without_extension(self):
        expected_extension = '.svg'
        expected_file_name = self.mimic_hashed_file_name(self.test_url, expected_extension)

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_hacked_svg_image_path(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_svg_with_extension(self):
        expected_extension = '.svg'

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_svg_image_path(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_scrubs_hacked_svg(self):
        hacked_svg = open(self.get_hacked_svg_image_path(), 'rb').read()

        responses.add(
            responses.GET,
            self.test_url,
            body=hacked_svg,
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        saved_svg_path = os.path.join('{base_url}/{file_name}'.format(
            base_url=default_storage.location,
            file_name=storage_name)
        )

        saved_svg = open(saved_svg_path, 'rb').read()

        self.assertNotIn(b'onload', saved_svg)
        self.assertNotIn(b'<script>', saved_svg)

    @responses.activate
    def test_png_without_extension(self):
        expected_extension = '.png'
        expected_file_name = self.mimic_hashed_file_name(self.test_url, expected_extension)

        responses.add(
                responses.GET,
                self.test_url,
                body=open(self.get_test_png_with_no_extension_image_path(), 'rb').read(),
                status=200
            )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_png_with_extension(self):
        expected_extension = '.png'
        expected_file_name = self.mimic_hashed_file_name(self.test_url, expected_extension)

        responses.add(
                responses.GET,
                self.test_url,
                body=open(self.get_test_png_image_path(), 'rb').read(),
                status=200
            )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_fetch_store_and_resize_png_height_from_800_to_512_1to1_ratio(self):
        expected_extension = '.png'

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_image_800x800(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types,
            resize_to_height=512
        )

        image = Image.open(os.path.join(self.path_to_mediafiles, storage_name))
        self.assertEqual(image.width, 512)
        self.assertEqual(image.height, 512)
        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_fetch_store_and_resize_png_height_from_800_to_512_16to9_ratio(self):
        expected_extension = '.png'

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_image_800x800(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types,
            resize_to_height=512,
            aspect_ratio=(1.77, 1)
        )

        image = Image.open(os.path.join(self.path_to_mediafiles, storage_name))

        self.assertEqual(image.height, 512)
        self.assertEqual(image.width, 906)
        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_jpeg_without_extension(self):
        expected_extension = '.jpeg'

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_jpeg_with_no_extension_image_path(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_jpeg_with_extension(self):
        expected_extension = '.jpeg'
        expected_file_name = self.mimic_hashed_file_name(self.test_url, expected_extension)

        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_jpeg_image_path(), 'rb').read(),
            status=200
        )

        status_code, storage_name = fetch_remote_file_to_storage(
            self.test_url,
            upload_to=self.test_uploaded_path,
            allowed_mime_types=self.mime_types
        )

        self.assertTrue(storage_name.endswith(expected_extension))
        self.assertTrue(default_storage.size(storage_name) > 0)

    @responses.activate
    def test_fetch_remote_file_to_storage_with_an_unsupported_mimetype_throws_UnsupportedMediaType(self):
        responses.add(
            responses.GET,
            self.test_url,
            body=open(self.get_test_jpeg_image_path(), 'rb').read(),
            status=200
        )

        with self.assertRaises(UnsupportedMediaType):
            status_code, storage_name = fetch_remote_file_to_storage(
                self.test_url,
                upload_to=self.test_uploaded_path,
                allowed_mime_types=['image/png', 'image/svg+xml']
            )
