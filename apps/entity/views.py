import six
from backpack.serializers_bcv1 import BadgeConnectErrorSerializer
from django import http
from django.db.models import ProtectedError
from entity.authentication import CSRFPermissionDenied
from entity.serializers import Rfc7591ErrorSerializer, V2ErrorSerializer
from rest_framework import exceptions, status, views
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.response import Response


def exception_handler(exc, context):
    version = context.get("kwargs", {}).get("version", "v1")

    if version in ["v2", "rfc7591"]:
        description = "miscellaneous error"
        field_errors = {}
        validation_errors = []

        if isinstance(exc, exceptions.ParseError):
            description = "bad request"
            validation_errors = [exc.detail]

            response_code = status.HTTP_400_BAD_REQUEST

        elif isinstance(exc, exceptions.ValidationError):
            description = "bad request"

            if isinstance(exc.detail, list):
                validation_errors = exc.detail
            elif isinstance(exc.detail, dict):
                field_errors = exc.detail
            elif isinstance(exc.detail, six.string_types):
                validation_errors = [exc.detail]

            response_code = status.HTTP_400_BAD_REQUEST

        elif isinstance(
            exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated)
        ):
            description = "no valid auth token found"
            response_code = status.HTTP_401_UNAUTHORIZED

        elif isinstance(exc, CSRFPermissionDenied):
            description = "no valid csrf token found"
            response_code = status.HTTP_401_UNAUTHORIZED

        elif isinstance(exc, (http.Http404, exceptions.PermissionDenied)):
            description = "entity not found or insufficient privileges"
            response_code = status.HTTP_404_NOT_FOUND

        elif isinstance(exc, ProtectedError):
            description, protected_objects = exc.args
            response_code = status.HTTP_400_BAD_REQUEST

        elif isinstance(exc, UnsupportedMediaType):
            description = exc.detail
            validation_errors = [exc.detail]
            response_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

        elif isinstance(exc, exceptions.APIException):
            field_errors = exc.detail
            response_code = exc.status_code

        else:
            # Unrecognized exception, return 500 error
            return None
        if version == "v2":
            serializer = V2ErrorSerializer(
                instance={},
                success=False,
                description=description,
                field_errors=field_errors,
                validation_errors=validation_errors,
            )
        else:
            serializer = Rfc7591ErrorSerializer(
                instance={},
                field_errors=field_errors,
                validation_errors=validation_errors,
            )
        return Response(serializer.data, status=response_code)

    elif version == "bcv1":
        # Badge Connect errors
        error = None
        status_code = status.HTTP_400_BAD_REQUEST
        status_text = "BAD_REQUEST"

        if isinstance(exc, exceptions.ParseError):
            error = exc.detail

        elif isinstance(exc, exceptions.ValidationError):
            error = exc.detail
            status_text = "REQUEST_VALIDATION_ERROR"

        elif isinstance(exc, exceptions.PermissionDenied):
            status_code = status.HTTP_401_UNAUTHORIZED
            status_text = "PERMISSION_DENIED"

        elif isinstance(
            exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated)
        ):
            status_code = status.HTTP_401_UNAUTHORIZED
            status_text = "UNAUTHENTICATED"

        elif isinstance(exc, exceptions.MethodNotAllowed):
            status_code = status.HTTP_405_METHOD_NOT_ALLOWED
            status_text = "METHOD_NOT_ALLOWED"

        serializer = BadgeConnectErrorSerializer(
            instance={}, error=error, status_text=status_text, status_code=status_code
        )
        return Response(serializer.data, status=status_code)

    else:
        # Use the default exception-handling logic for v1
        if isinstance(exc, ProtectedError):
            description, protected_objects = exc.args
            return Response(description, status=status.HTTP_400_BAD_REQUEST)
        return views.exception_handler(exc, context)
