from django_filters import CharFilter
from rest_framework.response import Response
from badgeuser.serializers_v3 import PreferenceSerializerV3
from badgeuser.models import UserPreference
from entity.api_v3 import EntityFilter, EntityViewSet
from issuer.permissions import BadgrOAuthTokenHasScope
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier


class PreferencesFilter(EntityFilter):
    key = CharFilter(field_name="key", lookup_expr="iexact")


class Preferences(EntityViewSet):
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        BadgrOAuthTokenHasScope,
    )
    valid_scopes = ["rw:profile"]
    filterset_class = PreferencesFilter
    serializer_class = PreferenceSerializerV3
    lookup_field = "key"
    http_method_names = ["get", "head", "options", "post", "delete"]

    def get_queryset(self):
        return UserPreference.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # Get the unique identifier from request data
        lookup_field = self.lookup_field
        lookup_value = request.data.get(lookup_field)

        if lookup_value:
            try:
                # Try to get the existing instance by lookup field
                instance = self.get_queryset().get(**{lookup_field: lookup_value})
                # If found, update it using the update method
                serializer = self.get_serializer(
                    instance, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                return Response(serializer.data)
            except UserPreference.DoesNotExist:
                # Instance not found, so create new
                pass

        # If no lookup value or instance not found, fallback to create new
        return super().create(request, *args, **kwargs)
