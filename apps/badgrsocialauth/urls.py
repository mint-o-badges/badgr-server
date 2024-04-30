import importlib
import logging

from allauth.socialaccount import providers
from badgrsocialauth.views import (
    BadgrAccountConnected,
    BadgrSocialAccountVerifyEmail,
    BadgrSocialEmailExists,
    BadgrSocialLogin,
    BadgrSocialLoginCancel,
    SamlEmailExistsRedirect,
    SamlFailureRedirect,
    SamlProvisionRedirect,
    SamlSuccessRedirect,
    assertion_consumer_service,
    saml2_render_or_redirect,
    saml2_sp_metadata,
)
from django.conf import settings
from django.conf.urls import url

urlpatterns = [
    url(
        r"^sociallogin",
        BadgrSocialLogin.as_view(permanent=False),
        name="socialaccount_login",
    ),
    # Intercept allauth cancel login view
    url(
        r"^cancellogin",
        BadgrSocialLoginCancel.as_view(permanent=False),
        name="socialaccount_login_cancelled",
    ),
    # Intercept allauth signup view (if account with given email already exists) and redirect to UI
    url(
        r"^emailexists",
        BadgrSocialEmailExists.as_view(permanent=False),
        name="socialaccount_signup",
    ),
    # Intercept allauth email verification view and redirect to UI
    url(
        r"^verifyemail",
        BadgrSocialAccountVerifyEmail.as_view(permanent=False),
        name="account_email_verification_sent",
    ),
    # Intercept allauth connections view (attached a new social account)
    url(
        r"^connected",
        BadgrAccountConnected.as_view(permanent=False),
        name="socialaccount_connections",
    ),
    # SAML2 Identity Provider
    url(
        r"^saml2/(?P<idp_name>[\w\.\-]+)/$", saml2_render_or_redirect, name="saml2login"
    ),
    url(
        r"^saml2/(?P<idp_name>[\w\.\-]+)/acs/",
        assertion_consumer_service,
        name="assertion_consumer_service",
    ),
    url(
        r"^saml2/(?P<idp_name>[\w\.\-]+)/metadata$",
        saml2_sp_metadata,
        name="saml2_sp_metadata",
    ),
    url(
        r"^saml2/loginfailure$",
        SamlFailureRedirect.as_view(permanent=False),
        name="saml2_failure",
    ),
    url(
        r"^saml2/loginsuccess$",
        SamlSuccessRedirect.as_view(permanent=False),
        name="saml2_success",
    ),
    url(
        r"^saml2/emailexists$",
        SamlEmailExistsRedirect.as_view(permanent=False),
        name="saml2_emailexists",
    ),
    url(
        r"^saml2/provision$",
        SamlProvisionRedirect.as_view(permanent=False),
        name="saml2_provision",
    ),
]

provider_list = providers.registry.get_list()
configured_providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", dict()).keys()
for provider in [p for p in provider_list if p.id in configured_providers]:
    try:
        prov_mod = importlib.import_module(provider.get_package() + ".urls")
    except ImportError:
        logging.getLogger(__name__).warning(
            "url import failed for %s socialaccount provider" % provider.id,
            exc_info=True,
        )
        continue
    prov_urlpatterns = getattr(prov_mod, "urlpatterns", None)
    if prov_urlpatterns:
        urlpatterns += prov_urlpatterns
