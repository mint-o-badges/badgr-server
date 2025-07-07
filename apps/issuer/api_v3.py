from django_filters import rest_framework as filters

from apispec_drf.decorators import (
    apispec_list_operation,
)

from entity.api_v3 import EntityFilter, EntityViewSet

from .serializers_v1 import (
    BadgeClassSerializerV1,
    IssuerSerializerV1,
    LearningPathSerializerV1,
)
from .models import BadgeClass, Issuer, LearningPath


class BadgeFilter(EntityFilter):
    tags = filters.CharFilter(field_name="badgeclasstag__name", lookup_expr="icontains")


class Badges(EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1
    filterset_class = BadgeFilter

    # only for apispec, get() does nothing on viewset
    @apispec_list_operation(
        "BadgeClass", summary="Get a list of Badges", tags=["BadgeClasses"]
    )
    def get(self, request, **kwargs):
        pass


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
