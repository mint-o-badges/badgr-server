from rest_framework import viewsets, serializers
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter
from django_filters import rest_framework as filters
from drf_spectacular.openapi import AutoSchema


class EntityLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20


class EntityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")


# Dummy serializer for the base EntityViewSet
# Subclasses will override with their actual serializer
class EntitySerializer(serializers.Serializer):
    """Placeholder serializer for EntityViewSet base class"""

    entity_id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False)
    created_at = serializers.DateTimeField(read_only=True)


class EntityViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for entity models.
    Subclasses MUST define:
    - queryset
    - serializer_class
    """

    pagination_class = EntityLimitOffsetPagination
    http_method_names = ["get", "head", "options"]
    lookup_field = "entity_id"
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = EntityFilter
    ordering_fields = ["name", "created_at"]

    # Default serializer - subclasses should override this
    serializer_class = EntitySerializer

    # Ensure schema is properly initialized for subclasses
    schema = AutoSchema()

    # Placeholder queryset - subclasses MUST override this
    queryset = None


class TagFilter(filters.BaseInFilter, filters.CharFilter):
    """
    A filter combining BaseInFilter and CharFilter allowing
    filtering for a list of comma-separated tags, returning
    only elements that have all the given tags set.
    """

    def filter(self, qs, value):
        if not value:
            return qs
        for tag in value:
            qs = qs.filter(**{f"{self.field_name}__icontains": tag})
        return qs
