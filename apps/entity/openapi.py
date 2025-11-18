from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import build_basic_type
from drf_spectacular.types import OpenApiTypes


class ExplicitCSRFSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for ExplicitCSRFSessionAuthentication.
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


class EntityRelatedFieldV2Extension(OpenApiSerializerFieldExtension):
    target_class = "entity.serializers.EntityRelatedFieldV2"

    def map_serializer_field(self, auto_schema, direction):
        return build_basic_type(OpenApiTypes.STR)
