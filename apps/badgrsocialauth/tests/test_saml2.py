import base64
import json
import os

from contextlib import closing
from urllib.parse import urlparse, parse_qs

from django.conf import settings
from django.utils.timezone import datetime
from django.shortcuts import reverse
from django.test import override_settings
from django.test.client import RequestFactory

from badgrsocialauth.models import Saml2Configuration, Saml2Account
from badgrsocialauth.views import auto_provision, saml2_client_for, create_saml_config_for
from badgrsocialauth.utils import set_session_authcode, set_session_badgr_app, userdata_from_saml_assertion

from badgeuser.models import CachedEmailAddress, BadgeUser

from mainsite.models import BadgrApp
from mainsite.tests import BadgrTestCase
from mainsite import TOP_DIR
from mainsite.utils import set_url_query_params

from saml2 import config, saml, BINDING_SOAP, BINDING_HTTP_REDIRECT, BINDING_HTTP_POST
from saml2.authn_context import authn_context_class_ref

# TODO: Revert to library code once library is fixed for python3
# from saml2.metadata import create_metadata_string
from badgrsocialauth.saml2_utils import create_metadata_string

from saml2.saml import AuthnContext, AuthnStatement, NAME_FORMAT_URI, NAMEID_FORMAT_PERSISTENT, \
    NAME_FORMAT_BASIC, AUTHN_PASSWORD_PROTECTED
from saml2.server import Server
from saml2.s_utils import MissingValue


class SAML2Tests(BadgrTestCase):
    def setUp(self):
        super(SAML2Tests, self).setUp()
        self.test_files_path = os.path.join(TOP_DIR, 'apps', 'badgrsocialauth', 'testfiles')
        self.idp_metadata_for_sp_config_path = os.path.join(
            self.test_files_path, 'idp-metadata-for-saml2configuration.xml')

        with open(self.idp_metadata_for_sp_config_path, 'r') as f:
            metadata_xml = f.read()
        self.config = Saml2Configuration.objects.create(
            metadata_conf_url="http://example.com",
            slug="saml2.test",
            cached_metadata=metadata_xml
        )
        self.badgr_app = BadgrApp.objects.create(
            ui_login_redirect="https://example.com",
            ui_signup_failure_redirect='https://example.com/fail'
        )
        self.badgr_app.is_default = True
        self.badgr_app.save()
        self.ipd_cert_path = os.path.join(self.test_files_path, 'idp-test-cert.pem')
        self.ipd_key_path = os.path.join(self.test_files_path, 'idp-test-key.pem')
        self.sp_acs_location = 'http://localhost:8000/account/saml2/{}/acs/'.format(self.config.slug)

    def _skip_if_xmlsec_binary_missing(self):
        xmlsec_binary_path = getattr(settings, 'XMLSEC_BINARY_PATH', None)
        if xmlsec_binary_path is None:
            self.skipTest("SKIPPING: In order to test XML Signing, XMLSEC_BINARY_PATH to xmlsec1 must be configured.")

    def _initiate_login(self, idp_name, badgr_app, user=None):
        # Sets a BadgrApp in the session for later redirect, allows setting of a session authcode
        url = set_url_query_params(reverse('socialaccount_login'), provider=idp_name)

        if user is not None:
            self.client.force_authenticate(user=user)
            preflight_response = self.client.get(
                reverse('v2_api_user_socialaccount_connect') + '?provider={}'.format(idp_name)
            )
            location = urlparse(preflight_response.data['result']['url'])
            url = '?'.join([location.path, location.query])  # strip server info from location

        return self.client.get(url, HTTP_REFERER=badgr_app.ui_login_redirect)

    def test_signed_authn_request_option_creates_signed_metadata(self):
        self._skip_if_xmlsec_binary_missing()

        self.config.use_signed_authn_request = True
        self.config.save()
        with override_settings(
                SAML_KEY_FILE=self.ipd_key_path,
                SAML_CERT_FILE=self.ipd_cert_path):
            saml_client, config = saml2_client_for(self.config)
            self.assertTrue(saml_client.authn_requests_signed)
            self.assertNotEqual(saml_client.sec.sec_backend, None)

    def test_signed_authn_request_option_returns_self_posting_form_populated_with_signed_metadata(self):
        self._skip_if_xmlsec_binary_missing()
        self.config.use_signed_authn_request = True
        self.config.save()
        with override_settings(
                SAML_KEY_FILE=self.ipd_key_path,
                SAML_CERT_FILE=self.ipd_cert_path):
            authn_request = self.config
            url = '/account/sociallogin?provider=' + authn_request.slug
            redirect_url = '/account/saml2/' + authn_request.slug + '/'
            response = self.client.get(url, follow=True)
            intermediate_url, intermediate_url_status = response.redirect_chain[0]

            # login redirect to saml2 login
            self.assertEqual(intermediate_url, redirect_url)
            self.assertEqual(intermediate_url_status, 302)
            # self populated form generated with metadata file from self.ipd_metadata_path
            self.assertEqual(response.status_code, 200)
            # changing attribute location of element md:SingleSignOnService necessitates updating this value
            self.assertIsNot(
                response.content.find(
                    b'<form action="https://example.com/saml2/idp/SSOService.php" method="post">'),
                -1)
            self.assertIsNot(
                response.content.find(b'<input type="hidden" name="SAMLRequest" value="'), -1)

    def test_create_saml2_client(self):
        Saml2Configuration.objects.create(metadata_conf_url="http://example.com",
                                          cached_metadata="<xml></xml>", slug="saml2.test2")
        client = saml2_client_for("saml2.test2")
        self.assertNotEqual(client, None)

    def test_oauth_to_saml2_redirection_flow(self):
        resp = self.client.get('/account/sociallogin?provider=' + self.config.slug)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/account/saml2/{}/'.format(self.config.slug))

    def test_login_with_registered_saml2_account(self):
        email = "test123@example.com"
        first_name = "firsty"
        last_name = "lastington"
        new_user = BadgeUser.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        # Auto verify emails
        cached_email = CachedEmailAddress.objects.get(email=email)
        cached_email.verified = True
        cached_email.save()
        Saml2Account.objects.create(config=self.config, user=new_user, uuid=email)
        BadgrApp.objects.create(ui_login_redirect="example.com", cors='example.com')
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)

    def test_login_with_unregistered_saml2_account(self):
        email = "test456@example.com"
        first_name = "firsty"
        last_name = "lastington"
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)

    def test_login_with_email_variant(self):
        email = "testemail@example.com"
        first_name = "firsty"
        last_name = "lastington"
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)

        email = "testEMAIL@example.com"
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertIn("authcode", resp.url)

    def test_saml2_login_with_conflicts(self):
        email = "test8679@example.com"
        email2 = "test234425@example.com"
        first_name = "firsty"
        last_name = "lastington"
        idp_name = self.config.slug
        badgr_app = self.badgr_app

        # email does not exist
        resp = auto_provision(
            None, ["different425@example.com"], first_name, last_name, self.config
        )
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)
        self.assertEqual(Saml2Account.objects.all().count(), 1)
        email_address = CachedEmailAddress.objects.get(email='different425@example.com')
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

        # email exists, but is unverified
        BadgeUser.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            send_confirmation=False
        )
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)
        email_address = CachedEmailAddress.objects.get(email=email)
        self.assertTrue(email_address.verified)
        self.assertTrue(email_address.primary)

        # Can auto provision again
        resp = auto_provision(None, [email], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)

        # email exists, but is verified
        BadgeUser.objects.create(
            email=email2,
            first_name=first_name,
            last_name=last_name,
            send_confirmation=False
        )
        cachedemail = CachedEmailAddress.objects.get(email=email2)
        cachedemail.verified = True
        cachedemail.save()
        saml_account_count = Saml2Account.objects.count()

        self._initiate_login(idp_name, badgr_app)
        resp = auto_provision(None, [email2], first_name, last_name, self.config)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authError=Could+not", resp.url)
        self.assertIn(self.config.slug, resp.url)
        self.assertEqual(saml_account_count, Saml2Account.objects.count(),
                "A Saml2Account must not have been created.")

        resp = self.client.get(resp.url)
        self.assertIn(self.config.slug, resp.url,
                "Query params are included in the response all the way back to the UI")

    def test_add_samlaccount_to_existing_user(self):
        # email exists, but is verified
        email = 'exampleuser@example.com'
        test_user = self.setup_user(
            email=email,
            token_scope='rw:profile rw:issuer rw:backpack'
        )

        preflight_response = self.client.get(
            reverse('v2_api_user_socialaccount_connect') + '?provider={}'.format(self.config.slug)
        )
        self.assertEqual(preflight_response.status_code, 200)
        location = urlparse(preflight_response.data['result']['url'])
        authcode = parse_qs(location.query)['authCode'][0]
        location = '?'.join([location.path, location.query])

        # the location now includes an auth code
        self.client.logout()
        response = self.client.get(location)
        self.assertEqual(response.status_code, 302)
        location = response._headers['location'][1]

        response = self.client.get(location)
        self.assertEqual(response.status_code, 302)

        # Can auto provision again
        rf = RequestFactory()
        fake_request = rf.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'saml_assertion': 'very fake'}
        )
        fake_request.session = dict()
        set_session_authcode(fake_request, authcode)

        resp = auto_provision(
            fake_request, [email], test_user.first_name, test_user.last_name, self.config
        )
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)
        Saml2Account.objects.get(user=test_user)

    def get_idp_config(self, meta=None):
        metadata_sp_1 = os.path.join(self.test_files_path, 'metadata_sp_1.xml')
        metadata_sp_2 = os.path.join(self.test_files_path, 'metadata_sp_2.xml')
        vo_metadata = os.path.join(self.test_files_path, 'vo_metadata.xml')
        attribute_map_dir = os.path.join(self.test_files_path, 'attributemaps')

        BASE = "http://localhost:8088"

        local_metadata = {"local": [metadata_sp_1, metadata_sp_2, vo_metadata]}
        metadata_source = local_metadata if meta is None else {'inline': [meta]}

        return {
            "entityid": "urn:mace:example.com:saml:roland:idp",
            "name": "Rolands IdP",
            "service": {
                "idp": {
                    "endpoints": {
                        "single_sign_on_service": [
                            ("%s/sso" % BASE, BINDING_HTTP_REDIRECT)],
                        "single_logout_service": [
                            ("%s/slo" % BASE, BINDING_SOAP),
                            ("%s/slop" % BASE, BINDING_HTTP_POST)]
                    },
                    "policy": {
                        "default": {
                            "lifetime": {"minutes": 15},
                            "attribute_restrictions": None,  # means all I have
                            "name_form": NAME_FORMAT_URI,
                        },
                        self.sp_acs_location: {
                            "lifetime": {"minutes": 5},
                            "nameid_format": NAMEID_FORMAT_PERSISTENT,
                        },
                        "https://example.com/sp": {
                            "lifetime": {"minutes": 5},
                            "nameid_format": NAMEID_FORMAT_PERSISTENT,
                            "name_form": NAME_FORMAT_BASIC
                        }
                    },
                },
            },
            "debug": 1,
            "key_file": self.ipd_key_path,
            "cert_file": self.ipd_cert_path,
            "xmlsec_binary": getattr(settings, 'XMLSEC_BINARY_PATH', None),
            "metadata": metadata_source,
            "attribute_map_dir": attribute_map_dir,
            "organization": {
                "name": "Exempel AB",
                "display_name": [("Exempel AB", "se"), ("Example Co.", "en")],
                "url": "http://www.example.com/roland",
            },
            "contact_person": [
                {
                    "given_name": "John",
                    "sur_name": "Smith",
                    "email_address": ["john.smith@example.com"],
                    "contact_type": "technical",
                },
            ],
        }

    def get_authn_response(self, idp_config, identity):
        with closing(SamlServer(idp_config)) as server:
            name_id = server.ident.transient_nameid(
                "urn:mace:example.com:saml:roland:idp", "id12")

            authn_context_ref = authn_context_class_ref(AUTHN_PASSWORD_PROTECTED)
            authn_context = AuthnContext(authn_context_class_ref=authn_context_ref)

            locality = saml.SubjectLocality()
            locality.address = "172.31.25.30"

            authn_statement = AuthnStatement(
                subject_locality=locality,
                authn_instant=datetime.now().isoformat(),
                authn_context=authn_context,
                session_index="id12"
            )

            return server.create_authn_response(
                identity,
                "id12",  # in_response_to
                self.sp_acs_location,  # consumer_url. config.sp.endpoints.assertion_consumer_service:["acs_endpoint"]
                self.sp_acs_location,  # sp_entity_id
                name_id=name_id,
                sign_assertion=True,
                sign_response=True,
                authn_statement=authn_statement
            )

    def test_saml2_create_account(self):
        self._skip_if_xmlsec_binary_missing()
        self.config.use_signed_authn_request = True
        self.config.save()

        with override_settings(SAML_KEY_FILE=self.ipd_key_path, SAML_CERT_FILE=self.ipd_cert_path):
            saml2config = self.config
            sp_config = config.SPConfig()
            sp_config.load(create_saml_config_for(saml2config))
            sp_metadata = create_metadata_string('', config=sp_config, sign=True)

        idp_config = self.get_idp_config(sp_metadata)

        identity = {"eduPersonAffiliation": ["staff", "member"],
                    "surName": ["Jeter"], "givenName": ["Derek"],
                    "mail": ["foo@gmail.com"],
                    "title": ["shortstop"]}

        authn_response = self.get_authn_response(idp_config, identity)

        base64_encoded_response_metadata = base64.b64encode(authn_response.encode('utf-8'))
        base_64_utf8_response_metadata = base64_encoded_response_metadata.decode('utf-8')

        response = self.client.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'SAMLResponse': base_64_utf8_response_metadata}
        )

        self.assertEqual(response.status_code, 302)

        location = response._headers['location'][1]
        response = self.client.get(location)

        self.assertEqual(Saml2Account.objects.count(), 1)
        self.assertEqual(CachedEmailAddress.objects.count(), 1)
        self.assertEqual(BadgeUser.objects.count(), 1)

    def test_saml2_create_account_multiple_emails(self):
        self._skip_if_xmlsec_binary_missing()
        self.config.use_signed_authn_request = True
        self.config.save()

        with override_settings(SAML_KEY_FILE=self.ipd_key_path, SAML_CERT_FILE=self.ipd_cert_path):
            saml2config = self.config
            sp_config = config.SPConfig()
            sp_config.load(create_saml_config_for(saml2config))
            sp_metadata = create_metadata_string('', config=sp_config, sign=True)

        idp_config = self.get_idp_config(sp_metadata)

        identity = {"eduPersonAffiliation": ["staff", "member"],
                    "surName": ["Jeter"], "givenName": ["Derek"],
                    "mail": ["foo@gmail.com", "foo2@gmail.com"],
                    "title": ["shortstop"]}

        authn_response = self.get_authn_response(idp_config, identity)

        base64_encoded_response_metadata = base64.b64encode(authn_response.encode('utf-8'))
        base_64_utf8_response_metadata = base64_encoded_response_metadata.decode('utf-8')

        response = self.client.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'SAMLResponse': base_64_utf8_response_metadata}
        )

        self.assertEqual(response.status_code, 302)

        location = response._headers['location'][1]
        response = self.client.get(location)

        self.assertEqual(Saml2Account.objects.count(), 1)
        self.assertEqual(CachedEmailAddress.objects.count(), 2)
        self.assertEqual(BadgeUser.objects.count(), 1)

    def test_saml2_create_account_multiple_email_assertions(self):
        self._skip_if_xmlsec_binary_missing()
        self.config.use_signed_authn_request = True
        self.config.save()

        with override_settings(SAML_KEY_FILE=self.ipd_key_path, SAML_CERT_FILE=self.ipd_cert_path):
            saml2config = self.config
            sp_config = config.SPConfig()
            sp_config.load(create_saml_config_for(saml2config))
            sp_metadata = create_metadata_string('', config=sp_config, sign=True)

        idp_config = self.get_idp_config(sp_metadata)

        identity = {"eduPersonAffiliation": ["staff", "member"],
                    "surName": ["Jeter"], "givenName": ["Derek"],
                    "mail": ["foo@gmail.com", "foo2@gmail.com"],
                    "email": ["foo3@gmail.com"],
                    "title": ["shortstop"]}

        authn_response = self.get_authn_response(idp_config, identity)

        base64_encoded_response_metadata = base64.b64encode(authn_response.encode('utf-8'))
        base_64_utf8_response_metadata = base64_encoded_response_metadata.decode('utf-8')

        response = self.client.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'SAMLResponse': base_64_utf8_response_metadata}
        )

        self.assertEqual(response.status_code, 302)

        location = response._headers['location'][1]
        response = self.client.get(location)

        self.assertEqual(Saml2Account.objects.count(), 1)
        self.assertEqual(CachedEmailAddress.objects.count(), 3)
        self.assertEqual(BadgeUser.objects.count(), 1)

    def test_saml2_create_account_multiple_email_already_taken(self):
        self._skip_if_xmlsec_binary_missing()
        self.config.use_signed_authn_request = True
        self.config.save()

        email = 'exampleuser@example.com'
        self.setup_user(
            email=email,
            token_scope='rw:profile rw:issuer rw:backpack'
        )

        with override_settings(SAML_KEY_FILE=self.ipd_key_path, SAML_CERT_FILE=self.ipd_cert_path):
            saml2config = self.config
            sp_config = config.SPConfig()
            sp_config.load(create_saml_config_for(saml2config))
            sp_metadata = create_metadata_string('', config=sp_config, sign=True)

        idp_config = self.get_idp_config(sp_metadata)

        identity = {"eduPersonAffiliation": ["staff", "member"],
                    "surName": ["Jeter"], "givenName": ["Derek"],
                    "mail": ["foo@gmail.com", "foo2@gmail.com"],
                    "email": ["exampleuser@example.com"],
                    "title": ["shortstop"]}

        authn_response = self.get_authn_response(idp_config, identity)

        base64_encoded_response_metadata = base64.b64encode(authn_response.encode('utf-8'))
        base_64_utf8_response_metadata = base64_encoded_response_metadata.decode('utf-8')

        response = self.client.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'SAMLResponse': base_64_utf8_response_metadata}
        )

        self.assertEqual(response.status_code, 302)

        location = response._headers['location'][1]
        response = self.client.get(location)

        self.assertEqual(Saml2Account.objects.count(), 0)
        self.assertEqual(CachedEmailAddress.objects.count(), 1)
        self.assertEqual(BadgeUser.objects.count(), 1)

    def test_add_samlaccount_to_existing_user_with_varying_email(self):
        email = 'exampleuser@example.com'
        t_user = self.setup_user(
            email=email,
            token_scope='rw:profile rw:issuer rw:backpack'
        )

        preflight_response = self.client.get(
            reverse('v2_api_user_socialaccount_connect') + '?provider={}'.format(self.config.slug)
        )
        self.assertEqual(preflight_response.status_code, 200)
        location = urlparse(preflight_response.data['result']['url'])
        authcode = parse_qs(location.query)['authCode'][0]
        location = '?'.join([location.path, location.query])

        # the location now includes an auth code
        self.client.logout()
        response = self.client.get(location)
        self.assertEqual(response.status_code, 302)
        location = response._headers['location'][1]
        response = self.client.get(location)
        self.assertEqual(response.status_code, 302)

        # Can auto provision again
        rf = RequestFactory()
        fake_request = rf.post(
            reverse('assertion_consumer_service', kwargs={'idp_name': self.config.slug}),
            {'saml_assertion': 'very fake'}
        )

        email2 = 'exampleuser_alt@example.com'
        resp = auto_provision(fake_request, [email2], t_user.first_name, t_user.last_name, self.config)
        self.assertEqual(resp.status_code, 302)

        fake_request.session = dict()
        set_session_authcode(fake_request, authcode)
        set_session_badgr_app(fake_request, self.badgr_app)
        fake_request.session['idp_name'] = self.config.slug

        resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("authToken", resp.url)
        self.assertIn(self.badgr_app.ui_login_redirect, resp.url)
        Saml2Account.objects.get(user=t_user)  # There is a Saml account associated with the user.
        CachedEmailAddress.objects.get(email=email2, user=t_user, verified=True, primary=False)  # User has the email.

        email3 = 'exampleuser_moredifferent@example.com'
        resp = auto_provision(fake_request, [email2, email3], t_user.first_name, t_user.last_name, self.config)

        CachedEmailAddress.objects.get(email=email3, user=t_user, verified=True, primary=False)  # User has new email.

    def test_can_extract_custom_userdata(self):
        self.config.custom_settings = json.dumps({
            'first_name': ['customMyClientFirstName']
        })
        self.config.save()
        reloaded_config = Saml2Configuration.objects.get(pk=self.config.pk)
        self.assertEqual(reloaded_config.custom_settings_data['email'], [], "default is set to an empty list")
        self.assertEqual(reloaded_config.custom_settings_data['first_name'], ['customMyClientFirstName'])

        fake_saml_assertion = {
            'emailaddress': ['moe@example.com'],
            'LastName': 'McMoe',
            'customMyClientFirstName': ['Moe']
        }

        self.assertEqual(
            userdata_from_saml_assertion(fake_saml_assertion, 'email', config=reloaded_config),
            fake_saml_assertion['emailaddress'][0]
        )
        self.assertEqual(
            userdata_from_saml_assertion(fake_saml_assertion, 'first_name', config=reloaded_config),
            fake_saml_assertion['customMyClientFirstName'][0]
        )
        self.assertEqual(
            userdata_from_saml_assertion(fake_saml_assertion, 'last_name', config=reloaded_config),
            fake_saml_assertion['LastName']
        )


class SamlServer(Server):
    def __int__(self, kwargs):
        super(SamlServer, self).__init__(**kwargs)

    def create_authn_response(self, identity, in_response_to, destination,
                              sp_entity_id, name_id_policy=None, userid=None,
                              name_id=None, authn=None, issuer=None,
                              sign_response=None, sign_assertion=None,
                              encrypt_cert_advice=None,
                              encrypt_cert_assertion=None,
                              encrypt_assertion=None,
                              encrypt_assertion_self_contained=True,
                              encrypted_advice_attributes=False, pefim=False,
                              sign_alg=None, digest_alg=None,
                              session_not_on_or_after=None,
                              **kwargs):
        """ Constructs an AuthenticationResponse

        :param identity: Information about an user
        :param in_response_to: The identifier of the authentication request
            this response is an answer to.
        :param destination: Where the response should be sent
        :param sp_entity_id: The entity identifier of the Service Provider
        :param name_id_policy: How the NameID should be constructed
        :param userid: The subject identifier
        :param name_id: The identifier of the subject. A saml.NameID instance.
        :param authn: Dictionary with information about the authentication
            context
        :param issuer: Issuer of the response
        :param sign_assertion: Whether the assertion should be signed or not.
        :param sign_response: Whether the response should be signed or not.
        :param encrypt_assertion: True if assertions should be encrypted.
        :param encrypt_assertion_self_contained: True if all encrypted
        assertions should have alla namespaces
        selfcontained.
        :param encrypted_advice_attributes: True if assertions in the advice
        element should be encrypted.
        :param encrypt_cert_advice: Certificate to be used for encryption of
        assertions in the advice element.
        :param encrypt_cert_assertion: Certificate to be used for encryption
        of assertions.
        :param sign_assertion: True if assertions should be signed.
        :param pefim: True if a response according to the PEFIM profile
        should be created.
        :return: A response instance
        """

        try:
            args = self.gather_authn_response_args(
                sp_entity_id, name_id_policy=name_id_policy, userid=userid,
                name_id=name_id, sign_response=sign_response,
                sign_assertion=sign_assertion,
                encrypt_cert_advice=encrypt_cert_advice,
                encrypt_cert_assertion=encrypt_cert_assertion,
                encrypt_assertion=encrypt_assertion,
                encrypt_assertion_self_contained=encrypt_assertion_self_contained,
                encrypted_advice_attributes=encrypted_advice_attributes,
                pefim=pefim, **kwargs)

            # authn statement is not returned from gather_authn_response_args()
            # make sure to include it in args if it was passed in initially
            if 'authn_statement' in kwargs:
                args['authn_statement'] = kwargs['authn_statement']
        except IOError as exc:
            response = self.create_error_response(in_response_to,
                                                  destination,
                                                  sp_entity_id,
                                                  exc, name_id)
            return ("%s" % response).split("\n")

        try:
            _authn = authn
            if (sign_assertion or sign_response) and \
                    self.sec.cert_handler.generate_cert():
                with self.lock:
                    self.sec.cert_handler.update_cert(True)
                    return self._authn_response(
                        in_response_to, destination, sp_entity_id, identity,
                        authn=_authn, issuer=issuer, pefim=pefim,
                        sign_alg=sign_alg, digest_alg=digest_alg,
                        session_not_on_or_after=session_not_on_or_after, **args)
            return self._authn_response(
                in_response_to, destination, sp_entity_id, identity,
                authn=_authn, issuer=issuer, pefim=pefim, sign_alg=sign_alg,
                digest_alg=digest_alg,
                session_not_on_or_after=session_not_on_or_after, **args)

        except MissingValue as exc:
            return self.create_error_response(in_response_to, destination,
                                              sp_entity_id, exc, name_id)
