# This file is copied from [here](https://dev.to/hesbon/customizing-mozilla-django-oidc-544p),
# which in turn is an almost exact copy of the original mozilla-django-oidc
# implementation of the ID token refresh middleware.

import logging
import time
from re import Pattern as re_Pattern

import requests
from django.urls import reverse
from django.utils.functional import cached_property
from mozilla_django_oidc.middleware import SessionRefresh as OIDCSessionRefresh

LOGGER = logging.getLogger(__name__)


class OIDCSessionRefreshMiddleware(OIDCSessionRefresh):
    @cached_property
    def exempt_urls(self):
        """Generate and return a set of url paths to exempt from SessionRefresh

        This takes the value of ``settings.OIDC_EXEMPT_URLS`` and appends three
        urls that mozilla-django-oidc uses. These values can be view names or
        absolute url paths.

        :returns: list of url paths (for example "/oidc/callback/")

        """
        exempt_urls = []
        for url in self.OIDC_EXEMPT_URLS:
            if not isinstance(url, re_Pattern):
                exempt_urls.append(url)
        return set(
            [url if url.startswith("/") else reverse(url) for url in exempt_urls]
        )

    def refresh_session(self, request):
        """Refresh the session with new data from the request session store."""

        # TODO: Potentially I'll have to retrieve the tokens differently
        refresh_token = request.session.get("oidc_refresh_token", None)

        token_refresh_payload = {
            "refresh_token": refresh_token,
            "client_id": self.get_settings("OIDC_RP_CLIENT_ID"),
            "client_secret": self.get_settings("OIDC_RP_CLIENT_SECRET"),
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(
                self.get_settings("OIDC_OP_TOKEN_ENDPOINT"), data=token_refresh_payload
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            LOGGER.error("Failed to refresh session: %s", e)
            return False
        data = response.json()
        # TODO: Potentially I'll have to store the tokens differently
        request.session.update(
            {
                "oidc_access_token": data.get("access_token"),
                "oidc_id_token_expiration": time.time() + data.get("expires_in"),
                "oidc_refresh_token": data.get("refresh_token"),
            }
        )
        return True

    def process_request(self, request):
        # TODO: This will have to be changed
        if not self.is_refreshable_url(request):
            LOGGER.debug("request is not refreshable")
            return

        # TODO: Potentially this'll have to be changed
        expiration = request.session.get("oidc_id_token_expiration", 0)
        now = time.time()
        if expiration > now:
            # The id_token is still valid, so we don't have to do anything.
            LOGGER.debug("id token is still valid (%s > %s)", expiration, now)
            return

        LOGGER.debug("id token has expired")
        if not self.refresh_session(request):
            # If we can't refresh the session, then we need to reauthenticate the user.
            # As per the default OIDCSessionRefresh implementation.
            return super().process_request(request)

        LOGGER.debug("session refreshed")
