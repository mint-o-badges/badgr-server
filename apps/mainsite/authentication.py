import datetime

import badgrlog
from django.conf import settings
from django.utils import timezone
from oauth2_provider.models import Application
from oauth2_provider.oauth2_backends import get_oauthlib_core
from rest_framework.authentication import BaseAuthentication, TokenAuthentication

badgrlogger = badgrlog.BadgrLogger()


class BadgrOAuth2Authentication(BaseAuthentication):
    www_authenticate_realm = "api"

    def authenticate_header(self, request):
        return 'Bearer realm="%s"' % self.www_authenticate_realm

    def authenticate(self, request):
        """
        Returns two-tuple of (user, token) if authentication succeeds,
        or None otherwise.
        """
        oauthlib_core = get_oauthlib_core()
        valid, r = oauthlib_core.verify_request(request, scopes=[])
        if valid:
            token_session_timeout = getattr(
                settings, "OAUTH2_TOKEN_SESSION_TIMEOUT_SECONDS", None
            )
            if token_session_timeout is not None:
                half_expiration_ahead = timezone.now() + datetime.timedelta(
                    seconds=token_session_timeout / 2
                )
                if r.access_token.expires < half_expiration_ahead:
                    r.access_token.expires = timezone.now() + datetime.timedelta(
                        seconds=token_session_timeout
                    )
                    r.access_token.save()
            if (
                r.client.authorization_grant_type
                == Application.GRANT_CLIENT_CREDENTIALS
            ):
                return r.client.user, r.access_token
            else:
                return r.access_token.user, r.access_token
        else:
            return None


class LoggedLegacyTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        authenticated_credentials = super(
            LoggedLegacyTokenAuthentication, self
        ).authenticate(request)
        if authenticated_credentials is not None:
            badgrlogger.event(
                badgrlog.DeprecatedApiAuthToken(
                    request, authenticated_credentials[0].username
                )
            )
        return authenticated_credentials
