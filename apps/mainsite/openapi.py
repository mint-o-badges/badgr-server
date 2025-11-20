from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BadgrOAuth2AuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for BadgrOAuth2Authentication.

    This tells drf-spectacular that BadgrOAuth2Authentication uses OAuth2
    with the authorization code flow. It will appear in the Swagger UI
    as an "Authorize" button where users can authenticate via OAuth2.
    """

    target_class = "mainsite.authentication.BadgrOAuth2Authentication"
    name = "oauth2"

    def get_security_definition(self, auto_schema):
        return {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "/o/authorize/",
                    "tokenUrl": "/o/token/",
                    "refreshUrl": "/o/token/",
                    "scopes": {
                        "read": "Read access to resources",
                        "write": "Write access to resources",
                    },
                }
            },
            "description": "OAuth2 authentication using django-oauth-toolkit",
        }


class LoggedLegacyTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for LoggedLegacyTokenAuthentication.

    This is a wrapper around DRF's TokenAuthentication that logs usage
    (because it's deprecated). We give it a unique name 'legacyToken' to
    avoid collision with the standard 'tokenAuth' name.
    """

    target_class = "mainsite.authentication.LoggedLegacyTokenAuthentication"
    name = "legacyToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Legacy token authentication. Format: `Token <your-token>`. "
            "This method is deprecated and logged for security auditing.",
        }
