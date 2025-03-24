from rest_framework import viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter
from django_filters import rest_framework as filters


class EntityLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20

class EntityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

class EntityViewSet(viewsets.ModelViewSet):
    pagination_class = EntityLimitOffsetPagination
    http_method_names = ['get', 'head', 'options']
    lookup_field = 'entity_id'
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = EntityFilter
    ordering_fields = ['name', 'created_at']