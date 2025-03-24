from rest_framework import viewsets, mixins
from rest_framework.pagination import LimitOffsetPagination

from apispec_drf.decorators import apispec_list_operation, apispec_post_operation, apispec_get_operation, \
    apispec_delete_operation, apispec_put_operation, apispec_operation

from .serializers_v1 import BadgeClassSerializerV1, IssuerSerializerV1, LearningPathSerializerV1
from .models import BadgeClass, Issuer, LearningPath

class EntityViewSet(viewsets.ModelViewSet):
    pagination_class = LimitOffsetPagination
    http_method_names = ['get', 'head', 'options']
    lookup_field = 'entity_id'

class Badges(EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1

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
    queryset = Issuer.objects.all()
    serializer_class = LearningPathSerializerV1