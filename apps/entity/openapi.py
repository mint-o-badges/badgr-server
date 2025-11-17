from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ExplicitCSRFSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for ExplicitCSRFSessionAuthentication.

    This is session-based authentication (using Django's session cookie)
    with explicit CSRF protection. It's typically used for browser-based
    clients that maintain a session after logging in through the web interface.
    """

    target_class = "entity.authentication.ExplicitCSRFSessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": "Session-based authentication with CSRF protection. "
            "Requires a valid Django session cookie and CSRF token in headers.",
        }
