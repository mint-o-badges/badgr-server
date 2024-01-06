# encoding: utf-8


import badgrlog
import datetime

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status

from backpack.models import BackpackCollection, BackpackBadgeShare, BackpackCollectionShare
from backpack.serializers_v1 import CollectionSerializerV1, LocalBadgeInstanceUploadSerializerV1
from backpack.serializers_v2 import BackpackAssertionSerializerV2, BackpackCollectionSerializerV2, \
    BackpackImportSerializerV2, BackpackAssertionAcceptanceSerializerV2
from entity.api import BaseEntityListView, BaseEntityDetailView
from issuer.models import BadgeInstance
from issuer.permissions import AuditedModelOwner, VerifiedEmailMatchesRecipientIdentifier, BadgrOAuthTokenHasScope
from issuer.public_api import ImagePropertyDetailView
from apispec_drf.decorators import apispec_list_operation, apispec_post_operation, apispec_get_operation, \
    apispec_delete_operation, apispec_put_operation, apispec_operation
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier, IsServerAdmin

from badgeuser.models import BadgeUser

logger = badgrlog.BadgrLogger()

_TRUE_VALUES = ['true', 't', 'on', 'yes', 'y', '1', 1, 1.0, True]
_FALSE_VALUES = ['false', 'f', 'off', 'no', 'n', '0', 0, 0.0, False]


def _scrub_boolean(boolean_str, default=None):
    if boolean_str in _TRUE_VALUES:
        return True
    if boolean_str in _FALSE_VALUES:
        return False
    return default


class BackpackAssertionList(BaseEntityListView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    create_event = badgrlog.BadgeUploaded
    permission_classes = (AuthenticatedWithVerifiedIdentifier,
            VerifiedEmailMatchesRecipientIdentifier,
            BadgrOAuthTokenHasScope)
    http_method_names = ('get', 'post')
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack'],
        'post': ['rw:backpack'],
    }
    include_defaults = {
        'include_expired': {'v1': 'true', 'v2': 'false'},
        'include_revoked': {'v1': 'false', 'v2': 'false'},
        'include_pending': {'v1': 'false', 'v2': 'false'},
    }

    def get_objects(self, request, **kwargs):
        version = kwargs.get('version', 'v1')
        include_expired = request.query_params.get(
            'include_expired', self.include_defaults['include_expired'][version]
        ).lower() in ['1', 'true']
        include_revoked = request.query_params.get(
            'include_revoked', self.include_defaults['include_revoked'][version]
        ).lower() in ['1', 'true']
        include_pending = request.query_params.get(
            'include_pending', self.include_defaults['include_pending'][version]
        ).lower() in ['1', 'true']

        def badge_filter(b):
            if ((b.acceptance == BadgeInstance.ACCEPTANCE_REJECTED)
                    or (not include_expired and b.expires_at is not None
                        and b.expires_at < timezone.now())
                    or (not include_revoked and b.revoked)
                    or (not include_pending and b.pending)):
                return False
            return True

        return list(filter(badge_filter, self.request.user.cached_badgeinstances()))

    @apispec_list_operation('Assertion',
                            summary="Get a list of Assertions in authenticated user's backpack ",
                            tags=['Backpack']
                            )
    def get(self, request, **kwargs):
        mykwargs = kwargs.copy()
        mykwargs['expands'] = []
        expands = request.GET.getlist('expand', [])

        if 'badgeclass' in expands:
            mykwargs['expands'].append('badgeclass')
        if 'issuer' in expands:
            mykwargs['expands'].append('issuer')

        return super(BackpackAssertionList, self).get(request, **mykwargs)

    @apispec_post_operation('Assertion',
                            summary="Upload a new Assertion to the backpack",
                            tags=['Backpack']
                            )
    def post(self, request, **kwargs):
        if kwargs.get('version', 'v1') == 'v1':
            try:
                return super(BackpackAssertionList, self).post(request, **kwargs)
            except serializers.ValidationError as e:
                self.log_not_created(e)
                raise e
        raise NotImplementedError("use BackpackImportBadge.post instead")

    def log_not_created(self, error):
        request = self.request
        user = request.user
        image_data = ''
        user_entity_id = ''
        error_name = ''
        error_result = ''

        if request.data.get('image', None) is not None:
            image_data = request.data.get('image', '')[:1024]

        if user is not None:
            user_entity_id = user.entity_id

        if len(error.detail) <= 1:
            # grab first error
            e = error.detail[0]
            error_name = e.get('name', '')
            error_result = e.get('result', '')

        invalid_badge_upload_report = badgrlog.InvalidBadgeUploadReport(image_data,
                user_entity_id, error_name, error_result)
        logger.event(badgrlog.InvalidBadgeUploaded(invalid_badge_upload_report))

    def get_context_data(self, **kwargs):
        context = super(BackpackAssertionList, self).get_context_data(**kwargs)
        context['format'] = self.request.query_params.get('json_format', 'v1')  # for /v1/earner/badges compat
        return context


class BackpackAssertionDetail(BaseEntityDetailView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    permission_classes = (AuthenticatedWithVerifiedIdentifier,
            VerifiedEmailMatchesRecipientIdentifier, BadgrOAuthTokenHasScope)
    http_method_names = ('get', 'delete', 'put')
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack'],
        'put': ['rw:backpack'],
        'delete': ['rw:backpack'],
    }

    def get_context_data(self, **kwargs):
        context = super(BackpackAssertionDetail, self).get_context_data(**kwargs)
        context['format'] = self.request.query_params.get('json_format', 'v1')  # for /v1/earner/badges compat
        return context

    @apispec_get_operation('BackpackAssertion',
                           summary="Get detail on an Assertion in the user's Backpack",
                           tags=['Backpack']
                           )
    def get(self, request, **kwargs):
        mykwargs = kwargs.copy()
        mykwargs['expands'] = []
        expands = request.GET.getlist('expand', [])

        if 'badgeclass' in expands:
            mykwargs['expands'].append('badgeclass')
        if 'issuer' in expands:
            mykwargs['expands'].append('issuer')

        return super(BackpackAssertionDetail, self).get(request, **mykwargs)

    @apispec_delete_operation('BackpackAssertion',
                              summary='Remove an assertion from the backpack',
                              tags=['Backpack']
                              )
    def delete(self, request, **kwargs):
        obj = self.get_object(request, **kwargs)
        related_collections = list(BackpackCollection.objects.filter(
            backpackcollectionbadgeinstance__badgeinstance=obj))

        if obj.source_url is None:
            obj.acceptance = BadgeInstance.ACCEPTANCE_REJECTED
            obj.save()
        else:
            obj.delete()

        for collection in related_collections:
            collection.save()

        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @apispec_put_operation('BackpackAssertion',
                           summary="Update acceptance of an Assertion in the user's Backpack",
                           tags=['Backpack']
                           )
    def put(self, request, **kwargs):
        fields_whitelist = ('acceptance',)
        data = {k: v for k, v in list(request.data.items()) if k in fields_whitelist}

        obj = self.get_object(request, **kwargs)
        if not self.has_object_permissions(request, obj):
            return Response(status=status.HTTP_404_NOT_FOUND)

        context = self.get_context_data(**kwargs)

        update_serializer = BackpackAssertionAcceptanceSerializerV2(obj, data, context=context)
        update_serializer.is_valid(raise_exception=True)
        update_serializer.save(updated_by=request.user)

        main_serializer_class = self.get_serializer_class()
        serializer = main_serializer_class(update_serializer.instance, context=context)

        return Response(serializer.data)


class BackpackAssertionDetailImage(ImagePropertyDetailView, BadgrOAuthTokenHasScope):
    model = BadgeInstance
    prop = 'image'
    valid_scopes = ['r:backpack', 'rw:backpack']


class BadgesFromUser(BaseEntityListView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    permission_classes = (IsServerAdmin,)
    valid_scopes = {
        'get': ['rw:serverAdmin'],
    }

    def get_objects(self, request, **kwargs):
        email = kwargs.get('email')
        try:
            user = BadgeUser.cached.get(email=email)
            return list(user.get_badges_from_user())
        except BadgeUser.DoesNotExist:
            raise ValueError('User not found')

    @apispec_get_operation(['BadgeInstance'],
                           summary='Get a list of Badges',
                           tags=['Backpack']
                           )
    def get(self, request, **kwargs):
        return super(BadgesFromUser, self).get(request, **kwargs)


class BackpackCollectionList(BaseEntityListView):
    model = BackpackCollection
    v1_serializer_class = CollectionSerializerV1
    v2_serializer_class = BackpackCollectionSerializerV2
    permission_classes = (AuthenticatedWithVerifiedIdentifier, AuditedModelOwner, BadgrOAuthTokenHasScope)
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack'],
        'post': ['rw:backpack'],
    }

    def get_objects(self, request, **kwargs):
        return self.request.user.cached_backpackcollections()

    @apispec_get_operation('Collection',
                           summary='Get a list of Collections',
                           tags=['Backpack']
                           )
    def get(self, request, **kwargs):
        return super(BackpackCollectionList, self).get(request, **kwargs)

    @apispec_post_operation('Collection',
                            summary='Create a new Collection',
                            tags=['Backpack']
                            )
    def post(self, request, **kwargs):
        return super(BackpackCollectionList, self).post(request, **kwargs)


class BackpackCollectionDetail(BaseEntityDetailView):
    model = BackpackCollection
    v1_serializer_class = CollectionSerializerV1
    v2_serializer_class = BackpackCollectionSerializerV2
    permission_classes = (AuthenticatedWithVerifiedIdentifier, AuditedModelOwner, BadgrOAuthTokenHasScope)
    valid_scopes = {
        'get': ['r:backpack', 'rw:backpack'],
        'post': ['rw:backpack'],
        'put': ['rw:backpack'],
        'delete': ['rw:backpack']
    }

    @apispec_get_operation('Collection',
                           summary='Get a single Collection',
                           tags=['Backpack']
                           )
    def get(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).get(request, **kwargs)

    @apispec_put_operation('Collection',
                           summary='Update a Collection',
                           tags=['Backpack']
                           )
    def put(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).put(request, **kwargs)

    @apispec_delete_operation('Collection',
                              summary='Delete a collection',
                              tags=['Backpack']
                              )
    def delete(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).delete(request, **kwargs)


class BackpackImportBadge(BaseEntityListView):
    v2_serializer_class = BackpackImportSerializerV2
    permission_classes = (AuthenticatedWithVerifiedIdentifier, BadgrOAuthTokenHasScope,)
    http_method_names = ('post',)
    valid_scopes = ['rw:backpack']

    @apispec_operation(
        summary="Import a new Assertion to the backpack",
        tags=['Backpack'],
        parameters=[
            {
                "in": "body",
                "name": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "format": "url",
                            "description": "URL to an OpenBadge compliant badge",
                            'required': False
                        },
                        "image": {
                            'type': "string",
                            'format': "data:image/png;base64",
                            'description': "base64 encoded Baked OpenBadge image",
                            'required': False
                        },
                        "assertion": {
                            'type': "json",
                            'description': "OpenBadge compliant json",
                            'required': False
                        },
                    }
                },
            }
        ]
    )
    def post(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        new_instance = serializer.save(created_by=request.user)
        self.log_create(new_instance)

        response_serializer = BackpackAssertionSerializerV2(new_instance, context=context)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ShareBackpackAssertion(BaseEntityDetailView):
    model = BadgeInstance
    permission_classes = (permissions.AllowAny,)  # this is AllowAny to support tracking sharing links in emails
    http_method_names = ('get',)
    allow_any_unauthenticated_access = True

    def get(self, request, **kwargs):
        """
        Share a single badge to a support share provider
        ---
        parameters:
            - name: provider
              description: The identifier of the provider to use. Supports 'facebook', 'linkedin'
              required: true
              type: string
              paramType: query
        """
        redirect = _scrub_boolean(request.query_params.get('redirect', "1"))

        provider = request.query_params.get('provider')
        if not provider:
            return Response({'error': "unspecified share provider"}, status=status.HTTP_400_BAD_REQUEST)
        provider = provider.lower()

        source = request.query_params.get('source', 'unknown')

        badge = self.get_object(request, **kwargs)
        if not badge:
            return Response(status=status.HTTP_404_NOT_FOUND)

        include_identifier = _scrub_boolean(request.query_params.get('include_identifier', False))

        share = BackpackBadgeShare(provider=provider, badgeinstance=badge, source=source)
        share_url = share.get_share_url(provider, include_identifier=include_identifier)
        if not share_url:
            return Response({'error': "invalid share provider"}, status=status.HTTP_400_BAD_REQUEST)

        share.save()
        logger.event(badgrlog.BadgeSharedEvent(badge, provider, datetime.datetime.now(), source))

        if redirect:
            headers = {'Location': share_url}
            return Response(status=status.HTTP_302_FOUND, headers=headers)
        else:
            return Response({'url': share_url})


class ShareBackpackCollection(BaseEntityDetailView):
    model = BackpackCollection
    permission_classes = (permissions.AllowAny,)  # this is AllowAny to support tracking sharing links in emails
    http_method_names = ('get',)

    def get(self, request, **kwargs):
        """
        Share a collection to a supported share provider
        ---
        parameters:
            - name: provider
              description: The identifier of the provider to use. Supports 'facebook', 'linkedin'
              required: true
              type: string
              paramType: query
        """
        redirect = _scrub_boolean(request.query_params.get('redirect', "1"))

        provider = request.query_params.get('provider')
        if not provider:
            return Response({'error': "unspecified share provider"}, status=status.HTTP_400_BAD_REQUEST)
        provider = provider.lower()

        source = request.query_params.get('source', 'unknown')

        collection = self.get_object(request, **kwargs)
        if not collection:
            return Response(status=status.HTTP_404_NOT_FOUND)

        share = BackpackCollectionShare(provider=provider, collection=collection, source=source)
        share_url = share.get_share_url(provider, title=collection.name, summary=collection.description)
        if not share_url:
            return Response({'error': "invalid share provider"}, status=status.HTTP_400_BAD_REQUEST)

        share.save()

        if redirect:
            headers = {'Location': share_url}
            return Response(status=status.HTTP_302_FOUND, headers=headers)
        else:
            return Response({'url': share_url})
