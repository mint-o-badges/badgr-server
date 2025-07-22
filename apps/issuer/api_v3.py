from django_filters import rest_framework as filters

from apispec_drf.decorators import (
    apispec_list_operation,
)

from entity.api_v3 import EntityFilter, EntityViewSet, TagFilter

from .serializers_v1 import (
    BadgeClassSerializerV1,
    IssuerSerializerV1,
    LearningPathSerializerV1,
)
from .models import BadgeClass, Issuer, LearningPath


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
