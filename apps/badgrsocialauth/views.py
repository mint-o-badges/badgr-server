import json
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

# TODO: Revert to library code once library is fixed for python3
# from saml2.metadata import create_metadata_string
from .saml2_utils import create_metadata_string

from allauth.account.adapter import get_adapter
from allauth.socialaccount.providers.base import AuthProcess
from django.contrib.auth import logout
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.urls import reverse, NoReverseMatch
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.generic import RedirectView
from django.shortcuts import redirect, render_to_response
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status

from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT

import logging

import requests

import base64

from badgeuser.authcode import authcode_for_accesstoken, accesstoken_for_authcode, encrypt_authcode, decrypt_authcode
from badgeuser.models import CachedEmailAddress, BadgeUser
from badgrsocialauth.models import Saml2Account, Saml2Configuration
from badgrsocialauth.utils import (set_session_badgr_app, get_session_authcode,
                                   get_session_verification_email, set_session_authcode,
                                   userdata_from_saml_assertion,
                                   )
from django.conf import settings
from mainsite.models import BadgrApp
from mainsite.utils import set_url_query_params

from saml2 import (
    BINDING_HTTP_POST,
    entity,
)
from saml2.client import Saml2Client
from saml2.config import Config as Saml2Config
from mainsite.models import AccessTokenProxy

logger = logging.getLogger(__name__)


class BadgrSocialLogin(RedirectView):
    def get(self, request, *args, **kwargs):
        try:
            logout(request)
            return super(BadgrSocialLogin, self).get(request, *args, **kwargs)
        except ValidationError as e:
            return HttpResponseBadRequest(e.message)
        except AuthenticationFailed as e:
            return HttpResponseForbidden(e.detail)

    def get_redirect_url(self):
        provider_name = self.request.GET.get('provider', None)
        if provider_name is None:
            raise ValidationError('No provider specified')

        badgr_app = BadgrApp.objects.get_current(request=self.request)
        if badgr_app is not None:
            set_session_badgr_app(self.request, badgr_app)
        else:
            raise ValidationError('Unable to save BadgrApp in session')

        self.request.session['source'] = self.request.GET.get('source', None)

        try:
            if 'saml2' in provider_name:
                redirect_url = reverse('saml2login', args=[provider_name])
                self.request.session['idp_name'] = provider_name
            else:
                redirect_url = reverse('{}_login'.format(provider_name))
        except (NoReverseMatch, TypeError,):
            raise ValidationError('No {} provider found'.format(provider_name))

        authcode = self.request.GET.get('authCode', None)
        if authcode is not None:
            set_session_authcode(self.request, authcode)
            return set_url_query_params(redirect_url, process=AuthProcess.CONNECT)
        else:
            return redirect_url


class BadgrSocialLoginCancel(RedirectView):
    def get_redirect_url(self):
        badgr_app = BadgrApp.objects.get_current(self.request)
        if badgr_app is not None:
            return set_url_query_params(badgr_app.ui_login_redirect)


class BadgrSocialEmailExists(RedirectView):
    def get_redirect_url(self):
        badgr_app = BadgrApp.objects.get_current(self.request)
        if badgr_app is not None:
            verification_email = self.request.session.get('verification_email', '')
            provider = self.request.session.get('socialaccount_sociallogin', {}).get('account', {}).get('provider', '')
            return set_url_query_params(
                badgr_app.ui_signup_failure_redirect,
                authError='An account already exists with provided email address',
                email=base64.urlsafe_b64encode(verification_email.encode('utf-8')),
                socialAuthSlug=provider
            )


class BadgrSocialAccountVerifyEmail(RedirectView):
    def get_redirect_url(self):
        badgr_app = BadgrApp.objects.get_current(self.request)
        verification_email = get_session_verification_email(self.request)

        if verification_email is not None:
            verification_email = urllib.parse.quote(verification_email).encode('utf-8')
        else:
            verification_email = b''

        if badgr_app is not None:
            base_64_email = base64.urlsafe_b64encode(verification_email)
            return urllib.parse.urljoin(
                badgr_app.ui_signup_success_redirect.rstrip('/') + '/', base_64_email.decode('utf-8')
            )


class BadgrAccountConnected(RedirectView):
    def get_redirect_url(self):
        badgr_app = BadgrApp.objects.get_current(self.request)
        if badgr_app is not None:
            return set_url_query_params(badgr_app.ui_connect_success_redirect)


"""

SAML2 Authentication Flow

"""


def saml2_client_for(idp_name=None):
    '''
    Given the name of an Identity Provider look up the Saml2Configuration and build a SAML Client. Return these.
    '''
    config = Saml2Configuration.objects.get(slug=idp_name)
    saml_config = create_saml_config_for(config)
    spConfig = Saml2Config()
    spConfig.load(saml_config)
    spConfig.allow_unknown_attributes = True
    saml_client = Saml2Client(config=spConfig)
    return saml_client, config


def create_saml_config_for(config):
    # SAML metadata changes very rarely, check for cached version first
    should_sign_authn_request = config.use_signed_authn_request

    metadata = None
    if config:
        metadata = config.cached_metadata

    if not metadata:
        r = requests.get(config.metadata_conf_url)
        metadata = r.text

    origin = getattr(settings, 'HTTP_ORIGIN')
    https_acs_url = origin + reverse('assertion_consumer_service', args=[config.slug])

    setting = {
        'metadata': {
            'inline': [metadata],
        },
        'entityid': https_acs_url,
        'service': {
            'sp': {
                'endpoints': {
                    'assertion_consumer_service': [
                        (https_acs_url, BINDING_HTTP_POST)
                    ],
                },
                # Don't verify that the incoming requests originate from us via
                # the built-in cache for authn request ids in pysaml2
                'allow_unsolicited': True,
                'authn_requests_signed': should_sign_authn_request,
                'logout_requests_signed': True,
                'want_assertions_signed': True,
                'want_response_signed': False,
            },
        },
    }
    if should_sign_authn_request:
        key_file = getattr(settings, 'SAML_KEY_FILE', None)
        if key_file is None:
            raise ImproperlyConfigured(
                "Signed Authn request requires the path to a PEM formatted file containing the certificates private key")

        cert_file = getattr(settings, 'SAML_CERT_FILE', None)
        if cert_file is None:
            raise ImproperlyConfigured(
                "Signed Authn request requires the path to a PEM formatted file containing the certificates public key")

        xmlsec_binary_path = getattr(settings, 'XMLSEC_BINARY_PATH', None)
        if xmlsec_binary_path is None:
            raise ImproperlyConfigured(
                "Signed Authn request requires the path to the xmlsec binary")

        setting['key_file'] = key_file
        setting['cert_file'] = cert_file
        # requires xmlsec binaries per https://pysaml2.readthedocs.io/en/latest/examples/sp.html
        setting['xmlsec_binary'] = xmlsec_binary_path
    return setting


def saml2_sp_metadata(request, idp_name):
    config = Saml2Configuration.objects.get(slug=idp_name)
    saml_config = create_saml_config_for(config)
    spConfig = Saml2Config()
    spConfig.load(saml_config)

    metadata = create_metadata_string('', config=spConfig, sign=config.use_signed_authn_request)
    return HttpResponse(metadata, content_type="text/xml")


def saml2_render_or_redirect(request, idp_name):
    config = Saml2Configuration.objects.get(slug=idp_name)
    saml_client, _ = saml2_client_for(idp_name)
    response = None

    if config.use_signed_authn_request:
        reqid, info = saml_client.prepare_for_authenticate(
            binding=BINDING_HTTP_POST,
            sign=True
        )
        response = HttpResponse(info['data'])
    else:
        reqid, info = saml_client.prepare_for_authenticate(binding=BINDING_HTTP_REDIRECT)
        redirect_url = None
        # Select the IdP URL to send the AuthN request to
        for key, value in info['headers']:
            if key == 'Location':
                redirect_url = value
        response = redirect(redirect_url)
        #  Read http://stackoverflow.com/a/5494469 and
        #  http://docs.oasis-open.org/security/saml/v2.0/saml-bindings-2.0-os.pdf
        #  We set those headers here as a "belt and suspenders" approach.
        response['Cache-Control'] = 'no-cache, no-store'
        response['Pragma'] = 'no-cache'

    badgr_app = BadgrApp.objects.get_current(request)
    request.session['badgr_app_pk'] = badgr_app.pk
    return response


def saml2_fail(**kwargs):
    return set_url_query_params(
        reverse('saml2_failure'), **kwargs
    )


def redirect_to_login_with_token(request, accesstoken):
    badgr_app = BadgrApp.objects.get_current(request)

    if badgr_app.use_auth_code_exchange:
        authcode = authcode_for_accesstoken(accesstoken)
        params = dict(authCode=authcode)
    else:
        params = dict(authToken=accesstoken.token)
    if badgr_app is not None:
        return set_url_query_params(badgr_app.ui_login_redirect, **params)


class SamlSuccessRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        authcode = self.request.GET.get('authcode', get_session_authcode(self.request))
        if not authcode:
            return saml2_fail(authError="Could not complete Saml login")

        accesstoken = accesstoken_for_authcode(authcode)
        return redirect_to_login_with_token(self.request, accesstoken)


class SamlProvisionRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        authcode = get_session_authcode(self.request)
        accesstoken = accesstoken_for_authcode(authcode)

        try:
            data = json.loads(decrypt_authcode(self.request.GET['request_id']))
            client, config = saml2_client_for(data['idp_name'])
            emails = data['emails']
            first_name = data['first_name']
            last_name = data['last_name']

        except (TypeError, ValueError, AttributeError, KeyError, Saml2Configuration.DoesNotExist,) as e:
            return saml2_fail(authError="Could not process Saml2 Response.")

        if CachedEmailAddress.cached.filter(email__in=emails).count() > 0:
            return saml2_fail(authError="Saml2 Response Processing interrupted. Email exists.")

        if accesstoken is not None and not accesstoken.is_expired():
            account_uuid = emails[0]
            Saml2Account.objects.create(config=config, user=accesstoken.user, uuid=account_uuid)
            for e in emails:
                CachedEmailAddress.objects.create(email=e, user=accesstoken.user, verified=True, primary=False)
            return redirect_to_login_with_token(self.request, accesstoken)

        # Email does not exist, nor does existing account. auto-provision new account and log in
        return redirect_user_to_login(saml2_new_account(emails, config, first_name, last_name, self.request))


class SamlFailureRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        badgr_app = BadgrApp.objects.get_current(self.request)
        if badgr_app is not None:
            params = {k: self.request.GET.get(k) for k in self.request.GET.keys()}
            return set_url_query_params(badgr_app.ui_signup_failure_redirect, **params)


class SamlEmailExistsRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        self.badgr_app = BadgrApp.objects.get_current(self.request)

        # Override: user has an appropriate authcode for the return flight to the UI
        authcode = get_session_authcode(self.request)
        email = self.request.GET.get('email')
        idp_name = self.request.session.get('idp_name')

        if not email or not authcode or not idp_name:
            return saml2_fail(
                authError="Could not associate SAML response with initial request", email=email, socialAuthSlug=idp_name
            )

        saml_client, config = saml2_client_for(idp_name)

        decoded_email = base64.urlsafe_b64decode(email).decode('utf-8')
        existing_email = CachedEmailAddress.cached.get(email=decoded_email)
        token = accesstoken_for_authcode(authcode)
        if token is not None and not token.is_expired() and token.user == existing_email.user:
            saml2_account = Saml2Account.objects.create(config=config, user=existing_email.user, uuid=decoded_email)
            return redirect_user_to_login(saml2_account.user)
        elif token is not None and token.is_expired():
            return saml2_fail(
                authError='Request is expired. Please try again.',
                email=email,
                socialAuthSlug=idp_name
            )

        # Fail: user does not have an appropriate authcode
        return saml2_fail(
            authError='An account already exists with provided email address',
            email=email,
            socialAuthSlug=idp_name
        )


@csrf_exempt
def assertion_consumer_service(request, idp_name):
    saml_client, config = saml2_client_for(idp_name)
    saml_response = request.POST.get('SAMLResponse')

    if saml_response is None:
        logger.error(
            'assertion_consumer_service: No SAMLResponse was sent to the system by the identity provider.'
        )
        return redirect(reverse(
            'saml2_failure',
            kwargs=dict(authError="No SAMLResponse was sent to the system by the identity provider")
        ))

    saml_info = "assertion_consumer_service: saml_client entityid:{}, reponse: {}".format(
        saml_client.config.entityid,
        saml_response
    )
    logger.info(saml_info)

    authn_response = saml_client.parse_authn_request_response(
        saml_response,
        entity.BINDING_HTTP_POST)

    if authn_response is None:
        logger.error(
            'assertion_consumer_service: SAMLResponse processing failed, resulting in no parsed data.'
        )
        return redirect(reverse(
            'saml2_failure',
            kwargs=dict(authError="Could not process SAMLResponse.")
        ))

    authn_response.get_identity()
    emails = userdata_from_saml_assertion(authn_response.ava, 'email', config, many=True)
    first_name = userdata_from_saml_assertion(authn_response.ava, 'first_name', config)
    last_name = userdata_from_saml_assertion(authn_response.ava, 'last_name', config)
    return auto_provision(request, emails, first_name, last_name, config)


def auto_provision(request, emails, first_name, last_name, config):
    # Get/Create account and redirect with token or with error message
    try:
        saml2_account = Saml2Account.objects.filter(uuid__in=emails, config=config).first()
    except Saml2Account.MultipleObjectsReturned:
        return redirect(reverse(
            'saml2_failure',
            kwargs=dict(authError="Multiple SAML accounts found.")
        ))

    if saml2_account:
        if CachedEmailAddress.objects.exclude(user=saml2_account.user).filter(email__in=emails).count() > 0:
            return redirect(reverse(
                'saml2_failure',
                kwargs=dict(authError="Multiple accounts using provided emails.")
            ))
        existing_emails = CachedEmailAddress.objects.filter(user=saml2_account.user).values_list('email', flat=True)
        processed_emails = [ee.lower() for ee in existing_emails]
        unused = [e for e in emails if e.lower() not in processed_emails]
        for e in unused:
            CachedEmailAddress.objects.create(email=e, user=saml2_account.user, verified=True)
        return redirect(redirect_user_to_login(saml2_account.user))

    # Check if any/all of the claimed emails already exist as verified
    claimed_emails = CachedEmailAddress.cached.filter(email__in=emails, verified=True)
    if claimed_emails.count() > 0:
        # If at least one is already verified, grab the first one and redirect with error
        email = claimed_emails.first().email
        return redirect(
            set_url_query_params(
                reverse('saml2_emailexists'),
                email=base64.urlsafe_b64encode(email.encode('utf-8')).decode('utf-8')
            )
        )

    existing_email = CachedEmailAddress.cached.filter(email__in=emails).first()
    if existing_email:
        # An email exists but is not verified, auto-provision account and log in
        new_account = saml2_new_account(emails, config, first_name, last_name, request)
        return redirect(redirect_user_to_login(new_account))
    else:
        provision_data = json.dumps({
            'first_name': first_name,
            'last_name': last_name,
            'emails': emails,
            'idp_name': config.slug  # TODO: actual property
        })
        return redirect(
            set_url_query_params(
                reverse('saml2_provision'),
                request_id=encrypt_authcode(provision_data),
            )
        )


def saml2_new_account(requested_emails, config, first_name='', last_name='', request=None):
    first_email = requested_emails[0]
    new_user = BadgeUser.objects.create(
        email=first_email,
        first_name=first_name,
        last_name=last_name,
        request=request,
        send_confirmation=False
    )
    for email in requested_emails[1:]:
        CachedEmailAddress.objects.create(email=email, user=new_user, verified=True)
    # Auto verify email
    cached_email = CachedEmailAddress.objects.get(email=first_email)
    cached_email.verified = True
    cached_email.save()
    Saml2Account.objects.create(config=config, user=new_user, uuid=first_email)
    return new_user


def redirect_user_to_login(user, token=None):
    if token is not None and not token.is_expired():
        accesstoken = token
    else:
        accesstoken = AccessTokenProxy.objects.generate_new_token_for_user(
            user, scope='rw:backpack rw:profile rw:issuer'
        )
    authcode = authcode_for_accesstoken(accesstoken)

    return set_url_query_params(
        reverse('saml2_success'),
        authcode=authcode
    )
