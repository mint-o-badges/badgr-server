from django_filters import rest_framework as filters
from rest_framework import viewsets, permissions
from rest_framework.response import Response

from apispec_drf.decorators import (
    apispec_list_operation,
)

from entity.api_v3 import EntityFilter, EntityViewSet, TagFilter

from .serializers_v1 import (
    BadgeClassSerializerV1,
    IssuerSerializerV1,
    LearningPathSerializerV1,
)
from .models import BadgeClass, BadgeClassTag, Issuer, LearningPath


class BadgeFilter(EntityFilter):
    tags = TagFilter(field_name="badgeclasstag__name", lookup_expr="icontains")


class Badges(EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1
    filterset_class = BadgeFilter
    ordering_fields = ["name", "created_at"]

    # only for apispec, get() does nothing on viewset
    @apispec_list_operation(
        "BadgeClass", summary="Get a list of Badges", tags=["BadgeClasses"]
    )
    def get(self, request, **kwargs):
        pass

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.distinct()


class BadgeTags(viewsets.ViewSet):
    """A ViewSet to fetch all available tags the existing Badges may be filtered by"""

    permission_classes = [permissions.AllowAny]  # anybody may see all badge tags

    def list(self, request, **kwargs):
        tag_names = (
            BadgeClassTag.objects.order_by("name")
            .values_list("name", flat=True)
            .distinct()
        )
        return Response(list(tag_names))


class Issuers(EntityViewSet):
    queryset = Issuer.objects.all()
    serializer_class = IssuerSerializerV1


class LearningPathFilter(EntityFilter):
    tags = filters.CharFilter(
        field_name="learningpathtag__name", lookup_expr="icontains"
    )


class LearningPaths(EntityViewSet):
    queryset = LearningPath.objects.all()
    serializer_class = LearningPathSerializerV1
    filterset_class = LearningPathFilter
