import datetime
from collections import OrderedDict, defaultdict
import json

import dateutil.parser
from allauth.account.adapter import get_adapter
from apispec_drf.decorators import (
    apispec_delete_operation,
    apispec_get_operation,
    apispec_list_operation,
    apispec_post_operation,
    apispec_put_operation,
)
from celery import shared_task
from celery.result import AsyncResult
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q, Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from entity.api import (
    BaseEntityDetailView,
    BaseEntityListView,
    BaseEntityView,
    UncachedPaginatedViewMixin,
    VersionedObjectMixin,
)
from entity.serializers import BaseSerializerV2, V2ErrorSerializer
from issuer.models import (
    BadgeClass,
    BadgeClassNetworkShare,
    BadgeInstance,
    Issuer,
    IssuerStaff,
    IssuerStaffRequest,
    LearningPath,
    NetworkInvite,
    NetworkMembership,
    QrCode,
    RequestedBadge,
)
from issuer.permissions import (
    ApprovedIssuersOnly,
    AuthorizationIsBadgrOAuthToken,
    BadgrOAuthTokenHasEntityScope,
    BadgrOAuthTokenHasScope,
    IsEditor,
    IsEditorButOwnerForDelete,
    IsNetworkMember,
    IsStaff,
    MayEditBadgeClass,
    MayIssueBadgeClass,
    MayIssueLearningPath,
    is_learningpath_editor,
    is_editor,
)
from issuer.serializers_v1 import (
    BadgeClassSerializerV1,
    BadgeInstanceSerializerV1,
    IssuerSerializerV1,
    IssuerStaffRequestSerializer,
    LearningPathParticipantSerializerV1,
    LearningPathSerializerV1,
    NetworkBadgeInstanceSerializerV1,
    NetworkInviteSerializer,
    NetworkSerializerV1,
    QrCodeSerializerV1,
    RequestedBadgeSerializer,
    BadgeClassNetworkShareSerializerV1,
)
from issuer.serializers_v2 import (
    BadgeClassSerializerV2,
    BadgeInstanceSerializerV2,
    IssuerAccessTokenSerializerV2,
    IssuerSerializerV2,
)
from mainsite.models import AccessTokenProxy, BadgrApp
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier, IsServerAdmin
from mainsite.serializers import CursorPaginatedListSerializer
from oauthlib.oauth2.rfc6749.tokens import random_token_generator
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import JsonResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from apps.mainsite.utils import OriginSetting
from issuer.services.image_composer import ImageComposer

import logging

logger = logging.getLogger("Badgr.Events")


class IssuerList(BaseEntityListView):
    """
    Issuer list resource for the authenticated user
    """

    model = Issuer
    v1_serializer_class = IssuerSerializerV1
    v2_serializer_class = IssuerSerializerV2
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
        )
    ]
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        # return self.request.user.cached_issuers()
        # Note: The issue with the commented line above is that When deleting an entity using the delete method,
        # it is removed from the database, but the cache is not invalidated. So this is a temporary workaround
        # till figuring out how to invalidate/refresh cache.
        # Force fresh data from the database
        return Issuer.objects.filter(
            staff__id=request.user.id, is_network=False
        ).distinct()

    @apispec_list_operation(
        "Issuer",
        summary="Get a list of Issuers for authenticated user",
        tags=["Issuers"],
    )
    def get(self, request, **kwargs):
        return super(IssuerList, self).get(request, **kwargs)

    @apispec_post_operation(
        "Issuer",
        summary="Create a new Issuer",
        tags=["Issuers"],
    )
    def post(self, request, **kwargs):
        return super(IssuerList, self).post(request, **kwargs)


class NetworkList(BaseEntityListView):
    """
    Network list resource for the authenticated user
    """

    model = Issuer
    v1_serializer_class = NetworkSerializerV1
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
        )
    ]
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        return Issuer.objects.filter(
            Q(staff__id=request.user.id)
            | Q(memberships__issuer__staff__id=request.user.id),
            is_network=True,
        ).distinct()

    @apispec_list_operation(
        "Network",
        summary="Get a list of Networks for authenticated user",
        tags=["Networks"],
    )
    def get(self, request, **kwargs):
        return super(NetworkList, self).get(request, **kwargs)

    @apispec_post_operation(
        "Network",
        summary="Create a new Network",
        tags=["Networks"],
    )
    def post(self, request, **kwargs):
        return super(NetworkList, self).post(request, **kwargs)


class NetworkUserIssuersList(BaseEntityListView):
    """
    List of issuers within a specific network that the authenticated user is editor or owner in
    """

    model = Issuer
    v1_serializer_class = IssuerSerializerV1
    v2_serializer_class = IssuerSerializerV2
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
        )
    ]
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        networkSlug = kwargs.get("networkSlug")

        if not networkSlug:
            return Issuer.objects.none()

        try:
            network = Issuer.objects.get(entity_id=networkSlug, is_network=True)
        except Issuer.DoesNotExist:
            return Issuer.objects.none()

        return Issuer.objects.filter(
            issuerstaff__user=request.user,
            issuerstaff__role__in=[IssuerStaff.ROLE_OWNER, IssuerStaff.ROLE_EDITOR],
            is_network=False,
            network_memberships__network_id=network.id,
        ).distinct()

    @apispec_list_operation(
        "Issuer",
        summary="Get a list of Issuers within a network for authenticated user",
        tags=["Networks", "Issuers"],
    )
    def get(self, request, **kwargs):
        return super(NetworkUserIssuersList, self).get(request, **kwargs)


class IssuerDetail(BaseEntityDetailView):
    model = Issuer
    v1_serializer_class = IssuerSerializerV1
    v2_serializer_class = IssuerSerializerV2
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & IsEditorButOwnerForDelete
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*", "rw:serverAdmin"]

    @apispec_get_operation(
        "Issuer",
        summary="Get a single Issuer",
        tags=["Issuers"],
    )
    def get(self, request, **kwargs):
        return super(IssuerDetail, self).get(request, **kwargs)

    @apispec_put_operation(
        "Issuer",
        summary="Update a single Issuer",
        tags=["Issuers"],
    )
    def put(self, request, **kwargs):
        return super(IssuerDetail, self).put(request, **kwargs)

    @apispec_delete_operation(
        "Issuer",
        summary="Delete a single Issuer",
        tags=["Issuers"],
    )
    def delete(self, request, **kwargs):
        return super(IssuerDetail, self).delete(request, **kwargs)


class NetworkIssuerDetail(BaseEntityDetailView):
    model = Issuer
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_object(self, network, issuer_slug):
        try:
            return network.partner_issuers.get(entity_id=issuer_slug)
        except Issuer.DoesNotExist:
            raise Http404("Issuer not found in this network")

    @apispec_delete_operation(
        "Issuer",
        summary="Remove an issuer from a network",
        description="Authenticated user must have owner, editor, or staff status on the Network",
        tags=["Issuers", "Network"],
    )
    def delete(self, request, slug, issuer_slug, **kwargs):
        try:
            network = Issuer.objects.get(entity_id=slug, is_network=True)
        except Issuer.DoesNotExist:
            raise Exception("Network not found")

        if not is_editor(request.user, network):
            return Response(
                {"error": "You are not authorized to remove this issuer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        issuer = self.get_object(network, issuer_slug)

        try:
            membership = NetworkMembership.objects.get(network=network, issuer=issuer)
            membership.delete()

        except NetworkMembership.DoesNotExist:
            return Response(
                {"error": "Membership not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        owners = issuer.cached_issuerstaff().filter(role=IssuerStaff.ROLE_OWNER)

        email_context = {"issuer": issuer, "network": network}

        adapter = get_adapter()

        for owner in owners:
            adapter.send_mail(
                "issuer/email/notify_issuer_network_update",
                owner.user.email,
                email_context,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class AllBadgeClassesList(UncachedPaginatedViewMixin, BaseEntityListView):
    """
    GET a list of badgeclasses within one issuer context or
    POST to create a new badgeclass within the issuer context
    """

    model = BadgeClass
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2
    valid_scopes = ["rw:issuer"]

    def get_queryset(self, request, **kwargs):
        if self.get_page_size(request) is None:
            return request.user.cached_badgeclasses()
        return BadgeClass.objects.filter(issuer__staff=request.user).order_by(
            "created_at"
        )

    @apispec_list_operation(
        "BadgeClass",
        summary="Get a list of BadgeClasses for authenticated user",
        tags=["BadgeClasses"],
    )
    def get(self, request, **kwargs):
        return super(AllBadgeClassesList, self).get(request, **kwargs)

    @apispec_post_operation(
        "BadgeClass",
        summary="Create a new BadgeClass",
        tags=["BadgeClasses"],
        parameters=[
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
        ],
    )
    def post(self, request, **kwargs):
        return super(AllBadgeClassesList, self).post(request, **kwargs)


class IssuerBadgeClassList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of badgeclasses within one issuer context or
    POST to create a new badgeclass within the issuer context
    """

    model = Issuer  # used by get_object()
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_queryset(self, request=None, **kwargs):
        issuer = self.get_object(request, **kwargs)

        if self.get_page_size(request) is None:
            return issuer.cached_badgeclasses()
        return BadgeClass.objects.filter(issuer=issuer)

    def get_context_data(self, **kwargs):
        context = super(IssuerBadgeClassList, self).get_context_data(**kwargs)
        context["issuer"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_list_operation(
        "BadgeClass",
        summary="Get a list of BadgeClasses for a single Issuer",
        description="Authenticated user must have owner, editor, or staff status on the Issuer",
        tags=["Issuers", "BadgeClasses"],
        parameters=[
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
        ],
    )
    def get(self, request, **kwargs):
        return super(IssuerBadgeClassList, self).get(request, **kwargs)

    @apispec_post_operation(
        "BadgeClass",
        summary="Create a new BadgeClass associated with an Issuer",
        description="Authenticated user must have owner, editor, or staff status on the Issuer",
        tags=["Issuers", "BadgeClasses"],
    )
    def post(self, request, **kwargs):
        self.get_object(request, **kwargs)  # trigger a has_object_permissions() check
        return super(IssuerBadgeClassList, self).post(request, **kwargs)


class NetworkBadgeClassesList(UncachedPaginatedViewMixin, BaseEntityListView):
    """
    GET a list of badgeclasses within a network context
    """

    model = BadgeClass
    # permission_classes = [

    #     IsServerAdmin
    #     | (AuthenticatedWithVerifiedIdentifier & IsNetworkMember)
    #     | BadgrOAuthTokenHasEntityScope
    # ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2
    valid_scopes = ["rw:issuer"]

    allow_any_unauthenticated_access = True

    def get_queryset(self, request=None, **kwargs):
        network_slug = kwargs.get("slug")
        if not network_slug:
            return BadgeClass.objects.none()

        try:
            return BadgeClass.objects.filter(
                issuer__entity_id=network_slug, issuer__is_network=True
            ).order_by("created_at")

        except Issuer.DoesNotExist:
            return BadgeClass.objects.none()

    @apispec_list_operation(
        "BadgeClass",
        summary="Get a list of BadgeClasses for network members",
        tags=["BadgeClasses"],
    )
    def get(self, request, **kwargs):
        return super(NetworkBadgeClassesList, self).get(request, **kwargs)


class IssuerAwardableBadgeClassList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of badgeclasses that this issuer can award (own badges + network badges + shared badges)
    """

    model = Issuer  # used by get_object()
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_object(self, request, **kwargs):
        issuerSlug = kwargs.get("slug")
        return Issuer.objects.get(entity_id=issuerSlug)

    def get_queryset(self, request=None, **kwargs):
        issuer = self.get_object(request, **kwargs)

        own_badges = BadgeClass.objects.filter(issuer=issuer)

        network_badges = BadgeClass.objects.filter(
            issuer__is_network=True, issuer__memberships__issuer=issuer
        )

        # Badges shared with networks where this issuer is a partner
        shared_badges = BadgeClass.objects.filter(
            network_shares__network__memberships__issuer=issuer,
            network_shares__is_active=True,
        )

        awardable_badges = own_badges.union(network_badges, shared_badges)

        return awardable_badges

    def get_context_data(self, **kwargs):
        context = super(IssuerAwardableBadgeClassList, self).get_context_data(**kwargs)
        context["issuer"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_list_operation(
        "BadgeClass",
        summary="Get a list of BadgeClasses that this Issuer can award",
        description="Returns own BadgeClasses plus BadgeClasses from networks where this issuer is a partner, plus BadgeClasses shared with those networks. Authenticated user must have owner, editor, or staff status on the Issuer",
        tags=["Issuers", "BadgeClasses"],
        parameters=[
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
        ],
    )
    def get(self, request, **kwargs):
        return super(IssuerAwardableBadgeClassList, self).get(request, **kwargs)


class IssuerLearningPathList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of learningpaths within one issuer context or
    POST to create a new learningpath within the issuer context
    """

    model = Issuer  # used by get_object()
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = LearningPathSerializerV1
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_queryset(self, request=None, **kwargs):
        issuer = self.get_object(request, **kwargs)
        return LearningPath.objects.filter(issuer=issuer)

    def get_context_data(self, **kwargs):
        context = super(IssuerLearningPathList, self).get_context_data(**kwargs)
        context["issuer"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_list_operation(
        "LearningPath",
        summary="Get a list of LearningPaths for a single Issuer",
        description="Authenticated user must have owner, editor, or staff status on the Issuer",
        tags=["Issuers", "LearningPaths"],
        parameters=[
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
        ],
    )
    def get(self, request, **kwargs):
        return super(IssuerLearningPathList, self).get(request, **kwargs)

    @apispec_post_operation(
        "LearningPath",
        summary="Create a new LearningPath associated with an Issuer",
        description="Authenticated user must have owner, editor, or staff status on the Issuer",
        tags=["Issuers", "LearningPath"],
    )
    def post(self, request, **kwargs):
        self.get_object(request, **kwargs)  # trigger a has_object_permissions() check
        return super(IssuerLearningPathList, self).post(request, **kwargs)


class LearningPathParticipantsList(BaseEntityView):
    """
    GET a list of learningpath participants
    """

    valid_scopes = ["rw:issuer"]

    def get_queryset(self):
        learning_path_slug = self.kwargs.get("slug")
        learning_path = LearningPath.objects.get(entity_id=learning_path_slug)
        badge_instances = BadgeInstance.objects.filter(
            badgeclass=learning_path.participationBadge,
            user__isnull=False,
            revoked=False,
        )
        return badge_instances

    @apispec_list_operation(
        "LearningPath",
        summary="Get a list of participants for this LearningPath",
        tags=["LearningPaths"],
    )
    def get(self, request, **kwargs):
        data = self.get_queryset()
        results = LearningPathParticipantSerializerV1(data, many=True).data
        return Response(results)


class BadgeClassDetail(BaseEntityDetailView):
    """
    GET details on one BadgeClass.
    PUT and DELETE should be restricted to BadgeClasses that haven't been issued yet.
    """

    model = BadgeClass
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & MayEditBadgeClass
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2

    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    @apispec_get_operation(
        "BadgeClass",
        summary="Get a single BadgeClass",
        tags=["BadgeClasses"],
    )
    def get(self, request, **kwargs):
        return super(BadgeClassDetail, self).get(request, **kwargs)

    @apispec_delete_operation(
        "BadgeClass",
        summary="Delete a BadgeClass",
        description="Restricted to owners or editors (not staff) of the corresponding Issuer.",
        tags=["BadgeClasses"],
        responses=OrderedDict(
            [
                (
                    "400",
                    {
                        "description": "BadgeClass couldn't be deleted. It may have already been issued."
                    },
                ),
            ]
        ),
    )
    def delete(self, request, **kwargs):
        base_entity = super(BadgeClassDetail, self)
        badge_class = base_entity.get_object(request, **kwargs)

        logger.info(
            "Deleting badge class '%s' requested by '%s'",
            badge_class.entity_id,
            request.user,
        )

        return base_entity.delete(request, **kwargs)

    @apispec_put_operation(
        "BadgeClass",
        summary="Update an existing BadgeClass.  Previously issued BadgeInstances will NOT be updated",
        tags=["BadgeClasses"],
    )
    def put(self, request, **kwargs):
        return super(BadgeClassDetail, self).put(request, **kwargs)


@shared_task
def process_batch_assertions(
    assertions, user_id, badgeclass_id, create_notification=False
):
    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)
        badgeclass = BadgeClass.objects.get(id=badgeclass_id)

        # Update assertions with create_notification
        assertions = [
            {**assertion, "create_notification": create_notification}
            for assertion in assertions
        ]

        context = {"badgeclass": badgeclass, "user": user}
        serializer = BadgeInstanceSerializerV1(
            many=True, data=assertions, context=context
        )
        if not serializer.is_valid():
            return {
                "success": False,
                "status": status.HTTP_400_BAD_REQUEST,
                "errors": serializer.errors,
            }

        serializer.save(created_by=user)
        return {
            "success": True,
            "status": status.HTTP_201_CREATED,
            "data": serializer.data,
        }

    except Exception as e:
        return {
            "success": False,
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error": str(e),
        }


class BatchAssertionsIssue(VersionedObjectMixin, BaseEntityView):
    model = BadgeClass  # used by .get_object()
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & MayIssueBadgeClass
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeInstanceSerializerV1
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_context_data(self, **kwargs):
        context = super(BatchAssertionsIssue, self).get_context_data(**kwargs)
        context["badgeclass"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_post_operation(
        "Assertion",
        summary="Issue multiple copies of the same BadgeClass to multiple recipients",
        tags=["Assertions"],
        parameters=[
            {
                "in": "body",
                "name": "body",
                "required": True,
                "schema": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Assertion"},
                },
            }
        ],
    )
    def get(self, request, task_id, **kwargs):
        task_result = AsyncResult(task_id)
        result = task_result.result if task_result.ready() else None

        if result and not result.get("success"):
            return Response(
                result, status=result.get("status", status.HTTP_400_BAD_REQUEST)
            )

        return Response(
            {"task_id": task_id, "status": task_result.status, "result": result}
        )

    def post(self, request, **kwargs):
        # verify the user has permission to the badgeclass
        badgeclass = self.get_object(request, **kwargs)
        assertions = request.data.get("assertions", [])
        if not self.has_object_permissions(request, badgeclass):
            return Response(status=HTTP_404_NOT_FOUND)

        try:
            create_notification = request.data.get("create_notification", False)
        except AttributeError:
            return Response(status=HTTP_400_BAD_REQUEST)

        # Start async task
        task = process_batch_assertions.delay(
            assertions=assertions,
            user_id=request.user.id,
            badgeclass_id=badgeclass.id,
            create_notification=create_notification,
        )

        return Response(
            {"task_id": str(task.id), "status": "processing"},
            status=status.HTTP_202_ACCEPTED,
        )


class BatchAssertionsRevoke(VersionedObjectMixin, BaseEntityView):
    model = BadgeInstance
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & MayEditBadgeClass
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_context_data(self, **kwargs):
        context = super(BatchAssertionsRevoke, self).get_context_data(**kwargs)
        context["badgeclass"] = self.get_object(self.request, **kwargs)
        return context

    def _process_revoke(self, request, revocation):
        response = {
            "revoked": False,
        }

        entity_id = revocation.get("entityId", None)
        revocation_reason = revocation.get("revocationReason", None)

        if entity_id is None:
            return dict(response, reason="entityId is required")

        response["entityId"] = entity_id

        if revocation_reason is None:
            return dict(response, reason="revocationReason is required")

        response["revocationReason"] = revocation_reason

        try:
            assertion = self.get_object(request, entity_id=entity_id)
        except Http404:
            return dict(response, reason="permission denied or object not found")

        try:
            assertion.revoke(revocation_reason)
        except Exception as e:
            return dict(response, reason=str(e))

        return dict(response, revoked=True)

    @apispec_post_operation(
        "Assertion",
        summary="Revoke multiple Assertions",
        tags=["Assertions"],
        parameters=[
            {
                "in": "body",
                "name": "body",
                "required": True,
                "schema": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Assertion"},
                },
            }
        ],
    )
    def post(self, request, **kwargs):
        result = [
            self._process_revoke(request, revocation)
            for revocation in self.request.data
        ]

        response_data = BaseSerializerV2.response_envelope(
            result=result, success=True, description="revoked badges"
        )

        return Response(status=HTTP_200_OK, data=response_data)


class BadgeInstanceList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of assertions for a single badgeclass
    POST to issue a new assertion
    """

    model = BadgeClass  # used by get_object()
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            # & MayIssueBadgeClass
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeInstanceSerializerV1
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_queryset(self, request=None, **kwargs):
        badgeclass = self.get_object(request, **kwargs)
        queryset = BadgeInstance.objects.filter(badgeclass=badgeclass)
        recipients = request.query_params.getlist("recipient", None)
        if recipients:
            queryset = queryset.filter(recipient_identifier__in=recipients)
        if request.query_params.get("include_expired", "").lower() not in ["1", "true"]:
            queryset = queryset.filter(
                Q(expires_at__gte=timezone.now()) | Q(expires_at__isnull=True)
            )
        if request.query_params.get("include_revoked", "").lower() not in ["1", "true"]:
            queryset = queryset.filter(revoked=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super(BadgeInstanceList, self).get_context_data(**kwargs)
        context["badgeclass"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_list_operation(
        "Assertion",
        summary="Get a list of Assertions for a single BadgeClass",
        tags=["Assertions", "BadgeClasses"],
        parameters=[
            {
                "in": "query",
                "name": "recipient",
                "type": "string",
                "description": "A recipient identifier to filter by",
            },
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
            {
                "in": "query",
                "name": "include_expired",
                "type": "boolean",
                "description": "Include expired assertions",
            },
            {
                "in": "query",
                "name": "include_revoked",
                "type": "boolean",
                "description": "Include revoked assertions",
            },
        ],
    )
    def get(self, request, **kwargs):
        # verify the user has permission to the badgeclass
        self.get_object(request, **kwargs)
        return super(BadgeInstanceList, self).get(request, **kwargs)

    @apispec_post_operation(
        "Assertion",
        summary="Issue an Assertion to a single recipient",
        tags=["Assertions", "BadgeClasses"],
    )
    def post(self, request, **kwargs):
        self.get_object(request, **kwargs)
        return super(BadgeInstanceList, self).post(request, **kwargs)


class IssuerNetworkBadgeClassList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of badge classes that this issuer has awarded
    where the badgeclass belongs to a network issuer
    OR has been shared with a network issuer,
    grouped by network issuer
    """

    model = Issuer
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeClassSerializerV1
    v2_serializer_class = BadgeClassSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_object(self, request=None, **kwargs):
        """
        Get the issuer by entity_id from the URL slug
        """
        issuer_slug = kwargs.get("issuerSlug")
        try:
            issuer = Issuer.objects.get(entity_id=issuer_slug)
            return issuer
        except Issuer.DoesNotExist:
            raise ValidationError(f"Issuer with slug '{issuer_slug}' not found")

    def get_queryset(self, request=None, **kwargs):
        """
        Get badge classes that this issuer has awarded instances of,
        where the badgeclass either:
          - belongs to a network issuer, OR
          - has been shared with a network
        """
        issuer = self.get_object(request, **kwargs)

        owned_badges = BadgeClass.objects.filter(
            issuer__is_network=True,
            badgeinstances__issuer=issuer,
        )

        shared_badges = BadgeClass.objects.filter(
            network_shares__network__is_network=True,
            badgeinstances__issuer=issuer,
            network_shares__is_active=True,
        )

        queryset = (owned_badges | shared_badges).distinct()

        queryset = queryset.annotate(
            awarded_count=Count(
                "badgeinstances", filter=Q(badgeinstances__issuer=issuer)
            )
        )

        return queryset

    @apispec_list_operation(
        "BadgeClass",
        summary="Get badge classes awarded by this issuer from networks (owned or shared), grouped by network",
        tags=["BadgeClasses", "Issuers", "Networks"],
    )
    def get(self, request, **kwargs):
        queryset = self.get_queryset(request, **kwargs)

        grouped_data = defaultdict(list)

        for badge_class in queryset:
            if badge_class.issuer.is_network:
                network_issuer = badge_class.issuer
            else:
                share = badge_class.network_shares.filter(is_active=True).first()
                if not share:
                    continue
                network_issuer = share.network

            badge_data = self.get_serializer_class()(badge_class).data
            badge_data["awarded_count"] = getattr(badge_class, "awarded_count", 0)

            grouped_data[network_issuer.entity_id].append(badge_data)

        response_data = []
        for network_issuer_slug, badge_classes in grouped_data.items():
            try:
                network_issuer = Issuer.objects.get(entity_id=network_issuer_slug)
                network_data = {
                    "network_issuer": {
                        "slug": network_issuer.entity_id,
                        "name": network_issuer.name,
                        "image": network_issuer.image.url
                        if network_issuer.image
                        else None,
                        "description": network_issuer.description,
                    },
                    "badge_classes": badge_classes,
                    "total_badges": len(badge_classes),
                    "total_instances_awarded": sum(
                        badge["awarded_count"] for badge in badge_classes
                    ),
                }
                response_data.append(network_data)
            except Issuer.DoesNotExist:
                continue

        response_data.sort(key=lambda x: x["network_issuer"]["name"])

        return Response(response_data)


class IssuerNetworkBadgeInstanceList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of badge instances issued by this issuer
    where the badgeclass belongs to a network issuer
    """

    model = Issuer
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeInstanceSerializerV1
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_object(self, request=None, **kwargs):
        """
        Get the issuer by entity_id from the URL slug
        """
        issuer_slug = kwargs.get("issuerSlug")
        try:
            issuer = Issuer.objects.get(entity_id=issuer_slug)
            return issuer
        except Issuer.DoesNotExist:
            raise ValidationError(f"Issuer with slug '{issuer_slug}' not found")

    def get_queryset(self, request=None, **kwargs):
        """
        Get badge instances issued by this issuer where the badgeclass
        belongs to a network issuer
        """
        issuer = self.get_object(request, **kwargs)

        queryset = BadgeInstance.objects.filter(
            issuer=issuer,
            badgeclass__issuer__is_network=True,
        )

        return queryset

    def get_context_data(self, **kwargs):
        context = super(IssuerNetworkBadgeInstanceList, self).get_context_data(**kwargs)
        context["issuer"] = self.get_object(self.request, **kwargs)
        return context

    def get_serializer_context(self):
        """
        Add user context for serializer, similar to your existing class
        """
        ctx = super(IssuerNetworkBadgeInstanceList, self).get_serializer_context()
        ctx["user"] = self.request.user
        return ctx

    @apispec_list_operation(
        "Assertion",
        summary="Get badge instances issued by this issuer from network badge classes",
        tags=["Assertions", "Issuers", "Networks"],
    )
    def get(self, request, **kwargs):
        self.get_object(request, **kwargs)
        return super(IssuerNetworkBadgeInstanceList, self).get(request, **kwargs)


class IssuerBadgeInstanceList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    Retrieve all assertions within one issuer
    """

    model = Issuer  # used by get_object()
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeInstanceSerializerV1
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_queryset(self, request=None, **kwargs):
        issuer = self.get_object(request, **kwargs)
        queryset = BadgeInstance.objects.filter(issuer=issuer)
        recipients = request.query_params.getlist("recipient", None)
        if recipients:
            queryset = queryset.filter(recipient_identifier__in=recipients)
        if request.query_params.get("include_expired", "").lower() not in ["1", "true"]:
            queryset = queryset.filter(
                Q(expires_at__gte=timezone.now()) | Q(expires_at__isnull=True)
            )
        if request.query_params.get("include_revoked", "").lower() not in ["1", "true"]:
            queryset = queryset.filter(revoked=False)
        return queryset

    @apispec_list_operation(
        "Assertion",
        summary="Get a list of Assertions for a single Issuer",
        tags=["Assertions", "Issuers"],
        parameters=[
            {
                "in": "query",
                "name": "recipient",
                "type": "string",
                "description": "A recipient identifier to filter by",
            },
            {
                "in": "query",
                "name": "num",
                "type": "string",
                "description": "Request pagination of results",
            },
            {
                "in": "query",
                "name": "include_expired",
                "type": "boolean",
                "description": "Include expired assertions",
            },
            {
                "in": "query",
                "name": "include_revoked",
                "type": "boolean",
                "description": "Include revoked assertions",
            },
        ],
    )
    def get(self, request, **kwargs):
        return super(IssuerBadgeInstanceList, self).get(request, **kwargs)

    @apispec_post_operation(
        "Assertion",
        summary="Issue a new Assertion to a recipient",
        tags=["Assertions", "Issuers"],
    )
    def post(self, request, **kwargs):
        kwargs["issuer"] = self.get_object(
            request, **kwargs
        )  # trigger a has_object_permissions() check
        return super(IssuerBadgeInstanceList, self).post(request, **kwargs)


class NetworkBadgeInstanceList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of assertions for a badgeclass across all network partner issuers
    """

    model = BadgeClass
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = NetworkBadgeInstanceSerializerV1
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_object(self, request=None, **kwargs):
        badgeSlug = kwargs.get("slug")
        badgeclass = BadgeClass.objects.get(entity_id=badgeSlug)
        if not badgeclass.issuer.is_network:
            raise ValidationError(
                "This endpoint is only available for badges created by networks"
            )
        return badgeclass

    def get_queryset(self, request=None, **kwargs):
        badgeclass = self.get_object(request, **kwargs)
        network = badgeclass.issuer

        queryset = BadgeInstance.objects.filter(
            badgeclass=badgeclass, issuer__network_memberships__network=network
        ).select_related("issuer", "user")

        return queryset

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["user"] = self.request.user
        return ctx

    def get(self, request, **kwargs):
        response = super().get(request, **kwargs)
        instances = response.data
        badgeclass = self.get_object(request, **kwargs)

        grouped_data = self.group_instances_by_issuer(instances, request, badgeclass)

        response.data = {"grouped_results": grouped_data}
        return response

    def _extract_slug_from_issuer_url(self, url):
        if not url:
            return None
        return url.rstrip("/").split("/")[-1]

    def group_instances_by_issuer(self, instances, request, badgeclass):
        grouped = {}
        request_user = request.user
        network_issuer = badgeclass.issuer
        partner_issuers = network_issuer.partner_issuers.all()

        for partner in partner_issuers:
            user_has_access = self.user_has_access_to_issuer(request_user, partner)
            grouped[partner.entity_id] = {
                "issuer": {
                    "slug": partner.entity_id,
                    "name": partner.name,
                    "image": partner.image.url if partner.image else None,
                },
                "has_access": user_has_access,
                "instances": [],
                "instance_count": 0,
            }

        for instance_data in instances:
            issuer_url = instance_data.get("issuer")
            issuer_slug = self._extract_slug_from_issuer_url(issuer_url)
            if issuer_slug and issuer_slug in grouped:
                if grouped[issuer_slug]["has_access"]:
                    grouped[issuer_slug]["instances"].append(instance_data)
                grouped[issuer_slug]["instance_count"] += 1

        for slug, group_data in grouped.items():
            if not group_data["has_access"]:
                partner = partner_issuers.get(entity_id=slug)
                group_data["instance_count"] = group_data["instance_count"]
                group_data["instances"] = []

        return list(grouped.values())

    def user_has_access_to_issuer(self, user, issuer):
        return user in issuer.staff.all()


class BadgeInstanceDetail(BaseEntityDetailView):
    """
    Endpoints for (GET)ting a single assertion or revoking a badge (DELETE)
    """

    model = BadgeInstance
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & MayEditBadgeClass
            & BadgrOAuthTokenHasScope
        )
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = BadgeInstanceSerializerV1
    v2_serializer_class = BadgeInstanceSerializerV2
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    @apispec_get_operation(
        "Assertion", summary="Get a single Assertion", tags=["Assertions"]
    )
    def get(self, request, **kwargs):
        return super(BadgeInstanceDetail, self).get(request, **kwargs)

    @apispec_delete_operation(
        "Assertion",
        summary="Revoke an Assertion",
        tags=["Assertions"],
        responses=OrderedDict(
            [("400", {"description": "Assertion is already revoked"})]
        ),
        parameters=[
            {
                "in": "body",
                "name": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "revocation_reason": {
                            "type": "string",
                            "format": "string",
                            "description": "The reason for revoking this assertion",
                            "required": False,
                        },
                    },
                },
            }
        ],
    )
    def delete(self, request, **kwargs):
        # verify the user has permission to the assertion
        assertion = self.get_object(request, **kwargs)
        if not self.has_object_permissions(request, assertion):
            return Response(status=HTTP_404_NOT_FOUND)

        revocation_reason = request.data.get("revocation_reason", None)
        if not revocation_reason:
            raise ValidationError({"revocation_reason": "This field is required"})

        try:
            assertion.revoke(revocation_reason)
        except DjangoValidationError as e:
            raise ValidationError(e.message)

        serializer = self.get_serializer_class()(
            assertion, context={"request": request}
        )

        logger.info(
            "Badge assertion '%s' revoking requested by '%s'",
            assertion.entity_id,
            request.user,
        )
        return Response(status=HTTP_200_OK, data=serializer.data)

    @apispec_put_operation(
        "Assertion",
        summary="Update an Assertion",
        tags=["Assertions"],
    )
    def put(self, request, **kwargs):
        return super(BadgeInstanceDetail, self).put(request, **kwargs)


class IssuerTokensList(BaseEntityListView):
    model = AccessTokenProxy
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        BadgrOAuthTokenHasScope,
        AuthorizationIsBadgrOAuthToken,
    )
    v2_serializer_class = IssuerAccessTokenSerializerV2
    valid_scopes = ["rw:issuer"]

    @apispec_post_operation(
        "AccessToken",
        summary="Retrieve issuer tokens",
        tags=["Issuers"],
    )
    def post(self, request, **kwargs):
        issuer_entityids = request.data.get("issuers", None)
        if not issuer_entityids:
            raise serializers.ValidationError({"issuers": "field is required"})

        issuers = []
        for issuer_entityid in issuer_entityids:
            try:
                issuer = Issuer.cached.get(entity_id=issuer_entityid)
                self.check_object_permissions(request, issuer)
            except Issuer.DoesNotExist:
                raise serializers.ValidationError({"issuers": "unknown issuer"})
            else:
                issuers.append(issuer)

        tokens = []
        expires = timezone.now() + datetime.timedelta(weeks=5200)

        application_user = request.auth.application.user

        for issuer in issuers:
            scope = "rw:issuer:{}".format(issuer.entity_id)

            if application_user:
                # grant application user staff access to issuer if needed
                staff, staff_created = IssuerStaff.cached.get_or_create(
                    issuer=issuer,
                    user=application_user,
                    defaults=dict(role=IssuerStaff.ROLE_STAFF),
                )

            accesstoken, created = AccessTokenProxy.objects.get_or_create(
                user=application_user,
                application=request.auth.application,
                scope=scope,
                defaults=dict(expires=expires, token=random_token_generator(request)),
            )
            tokens.append(
                {
                    "issuer": issuer.entity_id,
                    "token": accesstoken.token,
                    "expires": accesstoken.expires,
                }
            )

        serializer = IssuerAccessTokenSerializerV2(
            data=tokens, many=True, context=dict(request=request, kwargs=kwargs)
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class PaginatedAssertionsSinceSerializer(CursorPaginatedListSerializer):
    child = BadgeInstanceSerializerV2()

    def __init__(self, *args, **kwargs):
        self.timestamp = (
            timezone.now()
        )  # take timestamp now before SQL query is run in super.__init__
        super(PaginatedAssertionsSinceSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, data):
        representation = super(
            PaginatedAssertionsSinceSerializer, self
        ).to_representation(data)
        representation["timestamp"] = self.timestamp.isoformat()
        return representation


class AssertionsChangedSince(BaseEntityView):
    permission_classes = (BadgrOAuthTokenHasScope,)
    valid_scopes = ["r:issuer", "rw:issuer", "rw:serverAdmin"]

    def get_queryset(self, request, since=None):
        user = request.user

        # for efficiency, this is updated to no longer return assertions linked to applications
        # this will just fetch assertions for issuers that the user is a staff member for
        expr = Q(issuer__issuerstaff__user=user)

        if since is not None:
            expr &= Q(updated_at__gt=since)

        qs = BadgeInstance.objects.filter(expr).distinct()
        return qs

    def get(self, request, **kwargs):
        since = request.GET.get("since", None)
        if since is not None:
            try:
                since = dateutil.parser.isoparse(since)
            except ValueError:
                err = V2ErrorSerializer(
                    data={},
                    field_errors={"since": ["must be ISO-8601 format with time zone"]},
                    validation_errors=[],
                )
                err._success = False
                err._description = "bad request"
                err.is_valid(raise_exception=False)
                return Response(err.data, status=HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset(request, since=since)
        context = self.get_context_data(**kwargs)
        serializer = PaginatedAssertionsSinceSerializer(
            queryset=queryset, request=request, context=context
        )
        serializer.is_valid()
        return Response(serializer.data)


class PaginatedBadgeClassesSinceSerializer(CursorPaginatedListSerializer):
    child = BadgeClassSerializerV2()

    def __init__(self, *args, **kwargs):
        self.timestamp = (
            timezone.now()
        )  # take timestamp now before SQL query is run in super.__init__
        super(PaginatedBadgeClassesSinceSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, data):
        representation = super(
            PaginatedBadgeClassesSinceSerializer, self
        ).to_representation(data)
        representation["timestamp"] = self.timestamp.isoformat()
        return representation


class BadgeClassesChangedSince(BaseEntityView):
    permission_classes = (BadgrOAuthTokenHasScope,)
    valid_scopes = ["r:issuer", "rw:issuer", "rw:serverAdmin"]

    def get_queryset(self, request, since=None):
        user = request.user

        expr = Q(issuer__issuerstaff__user=user)

        if since is not None:
            expr &= Q(updated_at__gt=since)

        qs = BadgeClass.objects.filter(expr).distinct()
        return qs

    def get(self, request, **kwargs):
        since = request.GET.get("since", None)
        if since is not None:
            try:
                since = dateutil.parser.isoparse(since)
            except ValueError:
                err = V2ErrorSerializer(
                    data={},
                    field_errors={"since": ["must be ISO-8601 format with time zone"]},
                    validation_errors=[],
                )
                err._success = False
                err._description = "bad request"
                err.is_valid(raise_exception=False)
                return Response(err.data, status=HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset(request, since=since)
        context = self.get_context_data(**kwargs)
        serializer = PaginatedBadgeClassesSinceSerializer(
            queryset=queryset, request=request, context=context
        )
        serializer.is_valid()
        return Response(serializer.data)


class PaginatedIssuersSinceSerializer(CursorPaginatedListSerializer):
    child = IssuerSerializerV2()

    def __init__(self, *args, **kwargs):
        self.timestamp = (
            timezone.now()
        )  # take timestamp now before SQL query is run in super.__init__
        super(PaginatedIssuersSinceSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, data):
        representation = super(PaginatedIssuersSinceSerializer, self).to_representation(
            data
        )
        representation["timestamp"] = self.timestamp.isoformat()
        return representation


class IssuersChangedSince(BaseEntityView):
    permission_classes = (BadgrOAuthTokenHasScope,)
    valid_scopes = ["r:issuer", "rw:issuer", "rw:serverAdmin"]

    def get_queryset(self, request, since=None):
        user = request.user

        expr = Q(issuerstaff__user=user)

        if since is not None:
            expr &= Q(updated_at__gt=since)

        qs = Issuer.objects.filter(expr).distinct()
        return qs

    def get(self, request, **kwargs):
        since = request.GET.get("since", None)
        if since is not None:
            try:
                since = dateutil.parser.isoparse(since)
            except ValueError:
                err = V2ErrorSerializer(
                    data={},
                    field_errors={"since": ["must be ISO-8601 format with time zone"]},
                    validation_errors=[],
                )
                err._success = False
                err._description = "bad request"
                err.is_valid(raise_exception=False)
                return Response(err.data, status=HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset(request, since=since)
        context = self.get_context_data(**kwargs)
        serializer = PaginatedIssuersSinceSerializer(
            queryset=queryset, request=request, context=context
        )
        serializer.is_valid()
        return Response(serializer.data)


class QRCodeDetail(BaseEntityView):
    """
    QrCode list resource for the authenticated user
    """

    model = QrCode
    v1_serializer_class = QrCodeSerializerV1
    # v2_serializer_class = IssuerSerializerV2
    permission_classes = (BadgrOAuthTokenHasScope,)
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        badgeSlug = kwargs.get("badgeSlug")
        issuerSlug = kwargs.get("issuerSlug")

        try:
            issuer = Issuer.objects.get(entity_id=issuerSlug)
        except Issuer.DoesNotExist:
            return None

        if issuer.is_network:
            return QrCode.objects.filter(
                badgeclass__entity_id=badgeSlug,
                issuer__network_memberships__network=issuer,
            )

        return QrCode.objects.filter(
            badgeclass__entity_id=badgeSlug, issuer__entity_id=issuerSlug
        )

    def get_object(self, request, **kwargs):
        qr_code_id = kwargs.get("slug")
        return QrCode.objects.get(entity_id=qr_code_id)

    @apispec_list_operation(
        "QrCode",
        summary="Get a list of QrCodes for authenticated user",
        tags=["QrCodes"],
    )
    def get(self, request, **kwargs):
        serializer_class = self.get_serializer_class()

        if "slug" in kwargs:
            try:
                qr_code = self.get_object(request, **kwargs)
                serializer = serializer_class(qr_code)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except QrCode.DoesNotExist:
                return Response(
                    {"detail": "QR code not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            objects = self.get_objects(request, **kwargs)
            serializer = serializer_class(objects, many=True)

            return Response(serializer.data)

    @apispec_post_operation(
        "QrCode",
        summary="Create a new QrCode",
        tags=["QrCodes"],
    )
    def post(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=HTTP_201_CREATED)

    @apispec_put_operation(
        "QrCode",
        summary="Update a single QrCode",
        tags=["QrCodes"],
    )
    def put(self, request, **kwargs):
        qr_code = self.get_object(request, **kwargs)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(qr_code, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=HTTP_200_OK)

    @apispec_delete_operation(
        "QrCode",
        summary="Delete an existing QrCode",
        tags=["QrCodes"],
    )
    def delete(self, request, **kwargs):
        qr_code = self.get_object(request, **kwargs)
        qr_code.delete()
        return Response(status=HTTP_204_NO_CONTENT)


class NetworkBadgeQRCodeList(BaseEntityView):
    """
    QrCode list resource for a specific badge across all issuers in a network, grouped by issuer
    """

    model = QrCode
    v1_serializer_class = QrCodeSerializerV1
    permission_classes = (BadgrOAuthTokenHasScope,)
    valid_scopes = ["rw:issuer"]

    def get_network_badge_qrcodes(self, request, **kwargs):
        network_slug = kwargs.get("networkSlug")
        badge_slug = kwargs.get("badgeSlug")

        try:
            network = Issuer.objects.get(entity_id=network_slug, is_network=True)
        except Issuer.DoesNotExist:
            return None

        member_issuers = Issuer.objects.filter(network_memberships__network=network)

        qrcodes_by_issuer = {}
        for issuer in member_issuers:
            qrcodes = QrCode.objects.filter(
                issuer__entity_id=issuer.entity_id, badgeclass__entity_id=badge_slug
            )
            if qrcodes.exists():
                qrcodes_by_issuer[issuer.entity_id] = {
                    "issuer": IssuerSerializerV1(issuer).data,
                    "qrcodes": qrcodes,
                    "staff": self.user_is_staff(request.user, issuer),
                }

        return qrcodes_by_issuer

    @apispec_list_operation(
        "QrCode",
        summary="Get all QrCodes for a specific badge in a network grouped by issuer",
        tags=["QrCodes"],
    )
    def get(self, request, **kwargs):
        qrcodes_by_issuer = self.get_network_badge_qrcodes(request, **kwargs)

        if qrcodes_by_issuer is None:
            return Response(
                {"detail": "Network not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not qrcodes_by_issuer:
            return Response(
                {"detail": "No QR codes found for this badge in the network"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer_class = self.get_serializer_class()
        response_data = {}

        for issuer_slug, issuer_data in qrcodes_by_issuer.items():
            serializer = serializer_class(issuer_data["qrcodes"], many=True)
            response_data[issuer_slug] = {
                "issuer": issuer_data["issuer"],
                "qrcodes": serializer.data,
                "staff": issuer_data["staff"],
            }

        return Response(response_data, status=status.HTTP_200_OK)

    def user_is_staff(self, user, issuer):
        if not user or not user.is_authenticated:
            return False

        return issuer.staff_items.filter(user=user).exists()


class BadgeRequestList(BaseEntityListView):
    model = RequestedBadge
    v1_serializer_class = RequestedBadgeSerializer
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
        )
    ]
    valid_scopes = ["rw:issuer"]

    @apispec_delete_operation(
        "RequestedBadge",
        summary="Delete multiple badge requests",
        tags=["Requested Badges"],
    )
    def post(self, request, **kwargs):
        try:
            ids = request.data.get("ids", [])

            with transaction.atomic():
                deletion_queryset = RequestedBadge.objects.filter(
                    entity_id__in=ids,
                )

                found_ids = set(deletion_queryset.values_list("entity_id", flat=True))
                missing_ids = set(map(str, ids)) - set(map(str, found_ids))

                if missing_ids:
                    return Response(
                        {
                            "error": "Some requests not found",
                            "missing_ids": list(missing_ids),
                        },
                        status=HTTP_404_NOT_FOUND,
                    )

                deleted_count = deletion_queryset.delete()[0]

                return Response(
                    {
                        "message": f"Successfully deleted {deleted_count} badge requests",
                        "deleted_count": deleted_count,
                    },
                    status=HTTP_200_OK,
                )

        except DjangoValidationError as e:
            return Response({"error": str(e)}, status=HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred (" + str(e) + ")"},
                status=HTTP_400_BAD_REQUEST,
            )


class LearningPathDetail(BaseEntityDetailView):
    model = LearningPath
    v1_serializer_class = LearningPathSerializerV1
    permission_classes = (BadgrOAuthTokenHasScope, MayIssueLearningPath)
    valid_scopes = ["rw:issuer"]

    @apispec_get_operation(
        "LearningPath",
        summary="Get a single LearningPath",
        tags=["Learningpaths"],
    )
    def get(self, request, **kwargs):
        return super(LearningPathDetail, self).get(request, **kwargs)

    @apispec_put_operation(
        "LearningPath",
        summary="Update a single LearningPath",
        tags=["LearningPaths"],
    )
    def put(self, request, **kwargs):
        if not is_learningpath_editor(request.user, self.get_object(request, **kwargs)):
            return Response(
                {"error": "You are not authorized to delete this learning path."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super(LearningPathDetail, self).put(request, **kwargs)

    @apispec_delete_operation(
        "LearningPath",
        summary="Delete a single LearningPath",
        tags=["LearningPaths"],
    )
    def delete(self, request, **kwargs):
        if not is_learningpath_editor(request.user, self.get_object(request, **kwargs)):
            return Response(
                {"error": "You are not authorized to delete this learning path."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super(LearningPathDetail, self).delete(request, **kwargs)


class IssuerStaffRequestList(BaseEntityListView):
    model = IssuerStaffRequest
    v1_serializer_class = IssuerStaffRequestSerializer
    v2_serializer_class = IssuerStaffRequestSerializer
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
            & MayEditBadgeClass
        )
    ]
    valid_scopes = {
        "post": ["*"],
        "get": ["r:profile", "rw:profile"],
        "put": ["rw:profile"],
        "delete": ["rw:profile"],
    }

    @apispec_get_operation(
        "IssuerStaffRequest",
        summary="Get a list of staff membership requests for the institution",
        description="Use the id of the issuer to get a list of issuer staff requests",
        tags=["IssuerStaffRequest"],
    )
    def get_objects(self, request, **kwargs):
        issuerSlug = kwargs.get("issuerSlug")
        try:
            Issuer.objects.get(entity_id=issuerSlug)
        except Issuer.DoesNotExist:
            return Response(
                {"response": "Institution not found"}, status=status.HTTP_404_NOT_FOUND
            )

        return IssuerStaffRequest.objects.filter(
            issuer__entity_id=issuerSlug,
            revoked=False,
            status=IssuerStaffRequest.Status.PENDING,
        )

    def get(self, request, **kwargs):
        return super(IssuerStaffRequestList, self).get(request, **kwargs)


class IssuerStaffRequestDetail(BaseEntityDetailView):
    model = IssuerStaffRequest
    v1_serializer_class = IssuerStaffRequestSerializer
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
            & MayEditBadgeClass
        )
    ]
    valid_scopes = ["rw:issuer"]

    @apispec_get_operation(
        "IssuerStaffRequest",
        summary="Get a single IssuerStaffRequest",
        tags=["IssuerStaffRequest"],
    )
    def get(self, request, **kwargs):
        return super(IssuerStaffRequestDetail, self).get(request, **kwargs)

    @apispec_put_operation(
        "IssuerStaffRequest",
        summary="Update a single IssuerStaffRequest",
        tags=["IssuerStaffRequest"],
    )
    def put(self, request, **kwargs):
        if "confirm" in request.path:
            return self.confirm_request(request, **kwargs)
        return super(IssuerStaffRequestDetail, self).put(request, **kwargs)

    def confirm_request(self, request, **kwargs):
        try:
            staff_request = IssuerStaffRequest.objects.get(
                entity_id=kwargs.get("requestId")
            )

            badgrapp = BadgrApp.objects.get_by_id_or_default()

            if staff_request.status != IssuerStaffRequest.Status.PENDING:
                return Response(
                    {"detail": "Only pending requests can be confirmed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            staff_request.status = IssuerStaffRequest.Status.APPROVED
            staff_request.save()

            serializer = self.v1_serializer_class(staff_request)

            email_context = {
                "issuer": staff_request.issuer,
                "activate_url": badgrapp.ui_login_redirect.rstrip("/"),
                "call_to_action_label": "Jetzt loslegen",
            }
            get_adapter().send_mail(
                "account/email/staff_request_confirmed",
                staff_request.user.email,
                email_context,
            )
            return Response(serializer.data)

        except IssuerStaffRequest.DoesNotExist:
            return Response(
                {"detail": "Staff request not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @apispec_delete_operation(
        "IssuerStaffRequest",
        summary="Delete a single IssuerStaffRequest",
        tags=["IssuerStaffRequest"],
    )
    def delete(self, request, **kwargs):
        try:
            staff_request = IssuerStaffRequest.objects.get(
                entity_id=kwargs.get("requestId")
            )

            if staff_request.status != IssuerStaffRequest.Status.PENDING:
                if staff_request.status == IssuerStaffRequest.Status.REVOKED:
                    return Response(
                        {
                            "detail": "Request has already been revoked.",
                        },
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {"detail": "Only pending requests can be deleted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update status to rejected instead of hard delete
            staff_request.status = IssuerStaffRequest.Status.REJECTED
            staff_request.save()

            serializer = self.v1_serializer_class(staff_request)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except IssuerStaffRequest.DoesNotExist:
            return Response(
                {"detail": "Staff request not found"}, status=status.HTTP_404_NOT_FOUND
            )


class BadgeImageComposition(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            badgeSlug = request.data.get("badgeSlug")
            issuerSlug = request.data.get("issuerSlug")
            category = request.data.get("category")
            useIssuerImage = request.data.get("useIssuerImage", True)

            try:
                badge = BadgeClass.objects.get(entity_id=badgeSlug)
            except Issuer.DoesNotExist:
                return JsonResponse(
                    {"error": f"Badgeclass with slug {badgeSlug} not found"}, status=404
                )

            if not issuerSlug:
                return JsonResponse(
                    {"error": "Missing required field: issuerSlug"}, status=400
                )

            if not category:
                return JsonResponse(
                    {"error": "Missing required field: category"}, status=400
                )

            try:
                issuer = Issuer.objects.get(entity_id=issuerSlug)
            except Issuer.DoesNotExist:
                return JsonResponse(
                    {"error": f"Issuer with slug {issuerSlug} not found"}, status=404
                )

            issuer_image = issuer.image if (useIssuerImage and issuer.image) else None

            network_image = None

            composer = ImageComposer(category=category)

            extensions = badge.cached_extensions()
            org_img_ext = extensions.get(name="extensions:OrgImageExtension")
            original_image = json.loads(org_img_ext.original_json)["OrgImage"]

            if badge.cached_issuer.is_network:
                network_image = badge.cached_issuer.image
            else:
                shared_network = (
                    BadgeClassNetworkShare.objects.filter(
                        badgeclass=badge,
                        network__memberships__issuer=issuer,
                        is_active=True,
                    )
                    .select_related("network")
                    .first()
                )

                if shared_network and shared_network.network.image:
                    network_image = shared_network.network.image

            image_url = composer.compose_badge_from_uploaded_image(
                original_image, issuer_image, network_image
            )

            if not image_url:
                return JsonResponse(
                    {"error": "Failed to compose badge image"}, status=500
                )

            return JsonResponse(
                {
                    "success": True,
                    "image_url": image_url,
                    "message": "Badge image composed successfully",
                }
            )

        except Exception as e:
            print(f"Error in BadgeImageComposition: {e}")
            return JsonResponse(
                {"error": f"Internal server error: {str(e)}"}, status=500
            )


class NetworkInvitation(BaseEntityDetailView):
    model = NetworkInvite
    v1_serializer_class = NetworkInviteSerializer
    permission_classes = [
        IsServerAdmin | (AuthenticatedWithVerifiedIdentifier & BadgrOAuthTokenHasScope)
    ]
    valid_scopes = ["rw:issuer"]

    @apispec_get_operation(
        "NetworkInvite",
        summary="Get a single NetworkInvitation",
        tags=["NetworkInvite"],
    )
    def get(self, request, **kwargs):
        return super(NetworkInvitation, self).get(request, **kwargs)

    @apispec_post_operation(
        "NetworkInvite",
        summary="Create new network invitations",
        tags=["NetworkInvite"],
        responses=OrderedDict(
            [
                (
                    "201",
                    {"description": "Network invitation request created successfully"},
                ),
                ("400", {"description": "Bad request or validation error"}),
            ]
        ),
    )
    def post(self, request, **kwargs):
        try:
            network_slug = kwargs.get("networkSlug")
            network = Issuer.objects.get(entity_id=network_slug, is_network=True)
        except Issuer.DoesNotExist:
            return Response(
                {"response": "Network not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not is_editor(request.user, network):
            return Response(
                {"error": "You are not authorized to invite issuers."},
                status=status.HTTP_403_FORBIDDEN,
            )

        issuers_data = request.data
        if not issuers_data:
            return Response(
                {"response": "No issuers provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        slugs = []
        for issuer_data in issuers_data:
            slug = issuer_data.get("slug")
            if not slug:
                return Response(
                    {"response": "All issuers must have a slug"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            slugs.append(slug)

        issuers = Issuer.objects.filter(entity_id__in=slugs, is_network=False)
        found_slugs = set(issuers.values_list("entity_id", flat=True))

        missing_slugs = set(slugs) - found_slugs
        if missing_slugs:
            return Response(
                {"response": f"Issuers not found: {', '.join(missing_slugs)}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing_partner_ids = set(
            network.partner_issuers.filter(entity_id__in=slugs).values_list(
                "entity_id", flat=True
            )
        )

        if existing_partner_ids:
            existing_names = list(
                issuers.filter(entity_id__in=existing_partner_ids).values_list(
                    "name", flat=True
                )
            )
            return Response(
                {
                    "response": f"Diese Institutionen sind bereits Teil des Netzwerks: {', '.join(existing_names)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_invitations = NetworkInvite.objects.filter(
            issuer__entity_id__in=slugs,
            network=network,
            status=NetworkInvite.Status.PENDING,
        ).select_related("issuer")

        # if existing_invitations.exists():
        #     pending_names = [inv.issuer.name for inv in existing_invitations]
        #     return Response(
        #         {
        #             "response": f"Für diese Institutionen liegen bereits offene Einladungen vor: {', '.join(pending_names)}"
        #         },
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        try:
            with transaction.atomic():
                created_invitations = []
                for issuer in issuers:
                    invitation = NetworkInvite.objects.create(
                        issuer=issuer, network=network
                    )
                    created_invitations.append(invitation)

                    owners = issuer.cached_issuerstaff().filter(
                        role=IssuerStaff.ROLE_OWNER
                    )

                    email_context = {
                        "network": network,
                        "issuer": issuer,
                        "activate_url": OriginSetting.HTTP
                        + reverse(
                            "v1_api_user_confirm_network_invite",
                            current_app="badgeuser",
                            kwargs={
                                "inviteSlug": invitation.entity_id,
                            },
                        ),
                        "call_to_action_label": "Einladung bestätigen",
                    }

                    adapter = get_adapter()

                    for owner in owners:
                        adapter.send_mail(
                            "issuer/email/notify_issuer_network_invitation",
                            owner.user.email,
                            email_context,
                        )

                return Response(
                    {
                        "response": f"Successfully created {len(created_invitations)} network invitations",
                        "created_count": len(created_invitations),
                        "created_for": [inv.issuer.name for inv in created_invitations],
                    },
                    status=status.HTTP_201_CREATED,
                )
        except Exception as e:
            return Response(
                {"response": f"Failed to create invitations: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @apispec_put_operation(
        "NetworkInvite",
        summary="Update a single NetworkInvite",
        tags=["NetworkInvite"],
    )
    def put(self, request, **kwargs):
        if "confirm" in request.path:
            return self.confirm(request, **kwargs)
        return super(NetworkInvitation, self).put(request, **kwargs)

    def confirm(self, request, **kwargs):
        try:
            invitation = NetworkInvite.objects.get(entity_id=kwargs.get("slug"))

            if invitation.status != NetworkInvite.Status.PENDING:
                return Response(
                    {"detail": "Link expired"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if invitation.status == NetworkInvite.Status.APPROVED:
                return Response(
                    {"detail": "Issuer is already a partner of this network"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                invitation.status = NetworkInvite.Status.APPROVED
                invitation.acceptedOn = timezone.now()
                invitation.save()

                if invitation.issuer:
                    NetworkMembership.objects.get_or_create(
                        network=invitation.network, issuer=invitation.issuer
                    )

            serializer = self.v1_serializer_class(invitation)
            return Response(serializer.data)

        except NetworkInvite.DoesNotExist:
            return Response(
                {"detail": "Invitation not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @apispec_delete_operation(
        "NetworkInvite",
        summary="Revoke a single NetworkInvitation",
        tags=["NetworkInvite"],
    )
    def delete(self, request, **kwargs):
        try:
            invite = NetworkInvite.objects.get(entity_id=kwargs.get("slug"))

            if invite.status != IssuerStaffRequest.Status.PENDING:
                if invite.status == IssuerStaffRequest.Status.REVOKED:
                    return Response(
                        {
                            "detail": "Request has already been revoked.",
                        },
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {"detail": "Only pending requests can be revoked"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invite.status = IssuerStaffRequest.Status.REVOKED
            invite.save()

            serializer = self.v1_serializer_class(invite)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except IssuerStaffRequest.DoesNotExist:
            return Response(
                {"detail": "Network invitation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class NetworkInvitationList(BaseEntityListView):
    model = NetworkInvite
    v1_serializer_class = NetworkInviteSerializer
    permission_classes = [
        IsServerAdmin | (AuthenticatedWithVerifiedIdentifier & BadgrOAuthTokenHasScope)
    ]
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        status_filter = request.GET.get("status", "").lower()

        try:
            network = Issuer.objects.get(entity_id=kwargs.get("networkSlug"))
        except Issuer.DoesNotExist:
            Exception("Network not found")

        queryset = NetworkInvite.objects.filter(network=network)

        if status_filter == "pending":
            queryset = queryset.filter(status=NetworkInvite.Status.PENDING)
        elif status_filter == "approved":
            queryset = queryset.filter(status=NetworkInvite.Status.APPROVED)
        else:
            # return all
            pass

        return queryset

    @apispec_get_operation(
        "NetworkInvite",
        summary="Get network invitations with optional status filter",
        description="Get network invitations. Use 'status' query parameter to filter.",
        parameters=[
            {
                "name": "status",
                "in": "query",
                "description": "Filter invitations by status",
                "required": False,
                "schema": {
                    "type": "string",
                    "enum": ["pending", "approved"],
                    "default": "pending",
                },
            }
        ],
        tags=["NetworkInvite"],
    )
    def get(self, request, **kwargs):
        return super(NetworkInvitationList, self).get(request, **kwargs)


class NetworkSharedBadgesView(BaseEntityListView):
    """
    Get all badges shared with a specific network
    """

    model = BadgeClassNetworkShare
    v1_serializer_class = BadgeClassNetworkShareSerializerV1
    permission_classes = [AllowAny]  # partner badges are shown on public network page
    valid_scopes = ["rw:issuer"]

    allow_any_unauthenticated_access = True

    def get_objects(self, request, **kwargs):
        """Get all badge shares for a specific network"""

        entity_id = kwargs.get("entity_id")
        network = get_object_or_404(Issuer, entity_id=entity_id, is_network=True)

        return (
            BadgeClassNetworkShare.objects.filter(network=network, is_active=True)
            .select_related(
                "badgeclass", "badgeclass__issuer", "network", "shared_by_user"
            )
            .order_by("-shared_at")
        )

    @apispec_get_operation(
        "NetworkSharedBadges",
        summary="Get all badges shared with a network",
        tags=["Networks", "Badge Sharing"],
    )
    def get(self, request, **kwargs):
        """
        Get all badges that have been shared with a network.
        """

        return super(NetworkSharedBadgesView, self).get(request, **kwargs)


class IssuerSharedNetworkBadgesView(BaseEntityListView):
    """
    Get all badges that a specific issuer has shared with networks
    """

    model = BadgeClassNetworkShare
    v1_serializer_class = BadgeClassNetworkShareSerializerV1
    permission_classes = [AllowAny]
    valid_scopes = ["rw:issuer"]

    allow_any_unauthenticated_access = True

    def get_objects(self, request, **kwargs):
        """Get all badge shares from an issuer to any network"""

        entity_id = kwargs.get("entity_id")
        issuer = get_object_or_404(Issuer, entity_id=entity_id)

        return (
            BadgeClassNetworkShare.objects.filter(
                badgeclass__issuer=issuer, is_active=True
            )
            .select_related(
                "badgeclass", "badgeclass__issuer", "network", "shared_by_user"
            )
            .order_by("-shared_at")
        )

    @apispec_get_operation(
        "IssuerSharedNetworkBadges",
        summary="Get all badges shared by a specific issuer with networks",
        tags=["Issuers", "Badge Sharing"],
    )
    def get(self, request, **kwargs):
        """
        Get all badges that an issuer has shared with networks.
        """

        return super(IssuerSharedNetworkBadgesView, self).get(request, **kwargs)


class BadgeClassNetworkShareView(BaseEntityDetailView):
    """
    Share a badge class with a network
    """

    model = BadgeClassNetworkShare
    v1_serializer_class = BadgeClassNetworkShareSerializerV1
    permission_classes = [
        IsServerAdmin
        | (
            AuthenticatedWithVerifiedIdentifier
            & BadgrOAuthTokenHasScope
            & ApprovedIssuersOnly
        )
    ]
    valid_scopes = ["rw:issuer"]

    def get_objects(self, request, **kwargs):
        """Get all badge shares for the authenticated user's issuers"""
        user_issuers = Issuer.objects.filter(staff__id=request.user.id).values_list(
            "id", flat=True
        )

        return BadgeClassNetworkShare.objects.filter(
            badgeclass__issuer__id__in=user_issuers
        ).distinct()

    @apispec_post_operation(
        "BadgeClassNetworkShare",
        summary="Share a badge class with a network",
        tags=["Badge Sharing"],
    )
    def post(self, request, **kwargs):
        """
        Share a badge class with a network
        """
        badgeclass_id = kwargs.get("badgeSlug")
        network_id = kwargs.get("networkSlug")

        if not badgeclass_id or not network_id:
            return Response(
                {"error": "Both badgeclass_id and network_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        badgeclass = get_object_or_404(
            BadgeClass, entity_id=badgeclass_id, issuer__staff=request.user
        )

        network = get_object_or_404(Issuer, entity_id=network_id, is_network=True)

        if not NetworkMembership.objects.filter(
            network=network, issuer=badgeclass.issuer
        ).exists():
            return Response(
                {"error": "Your issuer is not a member of this network"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if BadgeClassNetworkShare.objects.filter(
            badgeclass=badgeclass, network=network
        ).exists():
            return Response(
                {"error": "Badge is already shared with this network"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        share = BadgeClassNetworkShare.objects.create(
            badgeclass=badgeclass, network=network, shared_by_user=request.user
        )

        extensions = badgeclass.cached_extensions()
        category_ext = extensions.get(name="extensions:CategoryExtension")
        category = json.loads(category_ext.original_json)["Category"]

        org_img_ext = extensions.get(name="extensions:OrgImageExtension")
        original_image = json.loads(org_img_ext.original_json)["OrgImage"]

        badgeclass.generate_badge_image(
            category, original_image, badgeclass.issuer.image, network.image
        )

        badgeclass.copy_permissions = BadgeClass.COPY_PERMISSIONS_NONE
        badgeclass.save(update_fields=["image", "copy_permissions"])

        serializer = self.get_serializer_class()(share)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
