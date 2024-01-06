import logging
import requests

from allauth.compat import parse_qsl
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.client import OAuth2Client, OAuth2Error
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider

logger = logging.getLogger(__name__)


class IdTokenAccount(ProviderAccount):
    def to_str(self):
        return self.account.extra_data.get(
            'name', super(IdTokenAccount, self).to_str())


class IdTokenProvider(OAuth2Provider):
    id = None  # e.g. 'someprovider'
    name = None  # e.g. 'Some Provider'
    account_class = IdTokenAccount

    def __init__(self, request):
        super(IdTokenProvider, self).__init__(request)

    def get_default_scope(self):
        return ['openid', 'profile', 'email']

    def extract_uid(self, data):
        logger.debug('{} | IdTokenProvider:extract_uid().data |  {}'.format(self.id, str(data)))
        return str(data['sub'])

    def extract_common_fields(self, data):
        logger.debug('{} | IdTokenProvider:extract_common_fields().data |  {}'.format(self.id, str(data)))
        return {
            'first_name': data['given_name'],
            'last_name': data['family_name'],
            'email': data['emails'][0],
        }


class IdTokenOAuth2Client(OAuth2Client):
    def get_access_token(self, code):
        data = {
            'redirect_uri': self.callback_url,
            'grant_type': 'authorization_code',
            'code': code}
        if self.basic_auth:
            auth = requests.auth.HTTPBasicAuth(
                self.consumer_key,
                self.consumer_secret)
        else:
            auth = None
            data.update({
                'client_id': self.consumer_key,
                'client_secret': self.consumer_secret
            })
        params = None
        self._strip_empty_keys(data)
        url = self.access_token_url
        if self.access_token_method == 'GET':
            params = data
            data = None
        # TODO: Proper exception handling
        resp = requests.request(
            self.access_token_method,
            url,
            params=params,
            data=data,
            headers=self.headers,
            auth=auth)

        access_token = None
        if resp.status_code in [200, 201]:
            # Weibo sends json via 'text/plain;charset=UTF-8'
            if resp.headers['content-type'].split(';')[0] == 'application/json' or resp.text[:2] == '{"':
                access_token = resp.json()
            else:
                access_token = dict(parse_qsl(resp.text))
        if not access_token or 'id_token' not in access_token:
            raise OAuth2Error('Error retrieving access token: %s'
                              % resp.content)
        return access_token
