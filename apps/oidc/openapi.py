from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OIDCAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for mozilla-django-oidc OIDCAuthentication.

    This handles OpenID Connect authentication, which is used for
    single sign-on with meinBildungsraum.
    """

    target_class = "mozilla_django_oidc.contrib.drf.OIDCAuthentication"
    name = "oidcAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "openIdConnect",
            "openIdConnectUrl": "",
            "description": "OpenID Connect authentication via meinBildungsraum",
        }
