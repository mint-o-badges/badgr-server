from collections import OrderedDict

from apispec_drf.decorators import apispec_get_operation, apispec_post_operation
from django.conf import settings
from django.shortcuts import reverse
from django.utils.dateparse import parse_datetime
from django.views.generic.base import RedirectView
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.views import APIView

from backpack.serializers_bcv1 import BackpackProfilesSerializerBC, BadgeConnectAssertionsSerializer, \
    BadgeConnectImportSerializer, BadgeConnectManifestSerializer
from badgeuser.models import BadgeUser
from entity.api import BaseEntityDetailView
from issuer.models import BadgeInstance
from issuer.permissions import BadgrOAuthTokenHasScope, VerifiedEmailMatchesRecipientIdentifier
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier
from mainsite.models import BadgrApp


BADGE_CONNECT_SCOPES = [
    "https://purl.imsglobal.org/spec/ob/v2p1/scope/assertion.readonly",
    "https://purl.imsglobal.org/spec/ob/v2p1/scope/assertion.create",
    "https://purl.imsglobal.org/spec/ob/v2p1/scope/profile.readonly",
]


def badge_connect_api_info(domain):
    try:
        badgr_app = BadgrApp.cached.get(cors=domain)
    except BadgrApp.DoesNotExist:
        return None

    return {
        "@context": "https://purl.imsglobal.org/spec/ob/v2p1/ob_v2p1.jsonld",
        "id": '{}{}'.format(
            settings.HTTP_ORIGIN,
            reverse('badge_connect_manifest', kwargs={'domain': domain})
        ),
        "badgeConnectAPI": [{
            "name": badgr_app.name,
            "image": '{}/images/logo.png'.format(settings.STATIC_URL),
            "apiBase": '{}{}'.format(settings.HTTP_ORIGIN, '/bcv1'),
            "version": "v1p0",
            "termsOfServiceUrl": "https://badgr.com/terms-of-service.html",
            "privacyPolicyUrl": "https://badgr.com/privacy-policy.html",
            "scopesOffered": BADGE_CONNECT_SCOPES,
            "registrationUrl": "{}{}".format(
                settings.HTTP_ORIGIN,
                reverse('oauth2_api_register')
            ),
            "authorizationUrl": "https://{}/auth/oauth2/authorize".format(domain),
            "tokenUrl": "{}{}".format(
                settings.HTTP_ORIGIN,
                reverse('oauth2_provider_token')
            ),
        }]
    }


class BadgeConnectManifestView(APIView):
    permission_classes = [AllowAny]

    @apispec_get_operation('BadgeConnectManifest',
                           summary='Fetch Badge Connect Manifest',
                           tags=['BadgeConnect'],
                           parameters=[{
                               "in": "query",
                               'name': 'domain',
                               'type': 'string',
                               'description': 'The CORS domain for the BadgrApp'
                               }
                           ]
                           )
    def get(self, request, **kwargs):
        data = badge_connect_api_info(kwargs.get('domain'))
        if data is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = BadgeConnectManifestSerializer(data)
        return Response(serializer.data)


class BadgeConnectManifestRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        badgr_app = BadgrApp.objects.get_current(self.request)
        return settings.HTTP_ORIGIN + reverse('badge_connect_manifest', kwargs={'domain': badgr_app.cors})


class BadgeConnectPagination(LimitOffsetPagination):
    def get_first_link(self):
        url = self.request.build_absolute_uri()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        return replace_query_param(url, self.offset_query_param, 0)

    def get_last_link(self):
        offset = self.count // self.limit
        if offset != 0 and self.count % (offset * self.limit) == 0:
            offset -= 1
        offset *= self.limit

        url = self.request.build_absolute_uri()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        if self.offset <= 0:
            return None

        url = self.request.build_absolute_uri()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.offset - self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_paginated_response(self, data):
        links = []
        if self.get_next_link():
            links.append('<%s>; rel="next"' % self.get_next_link())
        links.append('<%s>; rel="first"' % self.get_first_link())
        links.append('<%s>; rel="last"' % self.get_last_link())
        if self.get_previous_link():
            links.append('<%s>; rel="prev"' % self.get_previous_link())
        headers = dict(Link=','.join(links))
        return Response(data, headers=headers)


class BadgeConnectAssertionListView(ListCreateAPIView):
    model = BadgeInstance
    serializer_class = BadgeConnectAssertionsSerializer
    permission_classes = (AuthenticatedWithVerifiedIdentifier,
            VerifiedEmailMatchesRecipientIdentifier, BadgrOAuthTokenHasScope)
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack', 'https://purl.imsglobal.org/spec/ob/v2p1/scope/assertion.readonly'],
        'post': ['rw:backpack', 'https://purl.imsglobal.org/spec/ob/v2p1/scope/assertion.create'],
    }
    pagination_class = BadgeConnectPagination
    http_method_names = ('get', 'post')

    def get_queryset(self):
        qs = BadgeInstance.objects.filter(
                recipient_identifier__in=self.request.user.all_recipient_identifiers).order_by('-updated_at')
        if self.request.query_params.get('since', None):
            qs = qs.filter(updated_at__gte=parse_datetime(self.request.query_params.get('since')))
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BadgeConnectImportSerializer
        return super(BadgeConnectAssertionListView, self).get_serializer_class()

    @apispec_get_operation('BadgeConnectAssertions',
            summary='Get a list of Assertions',
            tags=['BadgeConnect'],
            parameters=[
                {
                    "in": "query",
                    'name': 'limit',
                    'type': 'integer',
                    'description': 'Indicate how many results should be retrieved in a single page.'
                    },
                {
                    "in": "query",
                    'name': 'offset',
                    'type': 'integer',
                    'description': 'Indicate the index of the first record to return (zero indexed).'
                    },
                {
                    "in": "query",
                    'name': 'limit',
                    'type': 'string',
                    'format': 'date-time',
                    'description': 'Retrieve Assertions that were created or updated '
                                   'after the provided timestamp. Must be an ISO 8601 '
                                   'compatible timestamp with a time zone indicator.'
                    },
                ]
            )
    def get(self, request, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset)
        return Response(serializer.data)

    @apispec_post_operation('BadgeConnectImport',
        summary='Import a Badge Assertion',
        tags=['BadgeConnect'],
        responses=OrderedDict([
            ("201", {
                'schema': {'$ref': '#/definitions/BadgeConnectImportResult'},
                'description': "Successfully created"
            }),
        ])
    )
    def post(self, request, **kwargs):
        return super(BadgeConnectAssertionListView, self).post(request, **kwargs)


class BadgeConnectProfileView(BaseEntityDetailView):
    model = BadgeUser
    bc_serializer_class = BackpackProfilesSerializerBC
    permission_classes = (AuthenticatedWithVerifiedIdentifier, BadgrOAuthTokenHasScope)
    http_method_names = ('get',)
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack', 'https://purl.imsglobal.org/spec/ob/v2p1/scope/profile.readonly'],
    }

    @apispec_get_operation('BadgeConnectProfiles',
            summary='Get Badge Connect user profile',
            tags=['BadgeConnect']
            )
    def get(self, request, **kwargs):
        """
        GET a single entity by its identifier
        """
        obj = request.user

        context = self.get_context_data(**kwargs)
        serializer_class = self.bc_serializer_class
        serializer = serializer_class([obj], context=context)
        return Response(serializer.data)

    def get_context_data(self, **kwargs):
        return {
            'request': self.request,
            'kwargs': kwargs,
        }

    def get_object(self, request, **kwargs):
        self.object = request.user
        return self.object
