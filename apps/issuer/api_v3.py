from rest_framework import viewsets, mixins
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.filters import OrderingFilter
from django_filters import rest_framework as filters

from apispec_drf.decorators import apispec_list_operation, apispec_post_operation, apispec_get_operation, \
    apispec_delete_operation, apispec_put_operation, apispec_operation

from .serializers_v1 import BadgeClassSerializerV1, IssuerSerializerV1, LearningPathSerializerV1
from .models import BadgeClass, Issuer, LearningPath

class EntityLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20

class EntityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

class BadgeFilter(EntityFilter):
    tags = filters.CharFilter(field_name='badgeclasstag__name', lookup_expr='icontains')

class LearningPathFilter(EntityFilter):
    tags = filters.CharFilter(field_name='learningpathtag__name', lookup_expr='icontains')

class EntityViewSet(viewsets.ModelViewSet):
    pagination_class = EntityLimitOffsetPagination
    http_method_names = ['get', 'head', 'options']
    lookup_field = 'entity_id'
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = EntityFilter
    ordering_fields = ['name', 'created_at']

class Badges(EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1
    filterset_class = BadgeFilter

    # only for apispec, get() does nothing on viewset
    @apispec_list_operation('BadgeClass',
        summary="Get a list of Badges",
        tags=['BadgeClasses']
    )
    def get(self, request, **kwargs):
        pass

class Issuers(EntityViewSet):
    queryset = Issuer.objects.all()
    serializer_class = IssuerSerializerV1

class LearningPaths(EntityViewSet):
    queryset = LearningPath.objects.all()
    serializer_class = LearningPathSerializerV1
    filterset_class = LearningPathFilter