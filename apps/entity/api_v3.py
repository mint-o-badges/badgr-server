from rest_framework import viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter
from django_filters import rest_framework as filters


class EntityLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20


class EntityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")


class EntityViewSet(viewsets.ModelViewSet):
    pagination_class = EntityLimitOffsetPagination
    http_method_names = ["get", "head", "options"]
    lookup_field = "entity_id"
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = EntityFilter
    ordering_fields = ["name", "created_at"]


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
