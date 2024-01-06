import oauth2_provider
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Allows only owners of an object to read or write it via the API
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsRequestUser(permissions.BasePermission):
    """
    Allows users to be able to act on their own profile, but not on others.
    """

    def has_object_permission(self, request, view, obj):
        return obj == request.user


class AuthenticatedWithVerifiedIdentifier(permissions.BasePermission):
    """
    Allows access only to authenticated users who have verified email addresses.
    """
    message = "This function only available to authenticated users with confirmed email addresses."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.verified


class IsServerAdmin(permissions.BasePermission):
    def check_permission(self, request):
        token = request.auth

        if token is None or not isinstance(token, oauth2_provider.models.AccessToken):
            return False

        token_scopes = set(token.scope.split())
        return 'rw:serverAdmin' in token_scopes

    def has_permission(self, request, view):
        return self.check_permission(request)

    def has_object_permission(self, request, view, obj):
        return self.check_permission(request)
