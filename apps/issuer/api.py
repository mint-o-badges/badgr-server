import datetime
from collections import OrderedDict

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
from django.db.models import Q
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from apps.badgeuser.api import BaseRedirectView
from rest_framework import permissions

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
    BadgeInstance,
    Issuer,
    IssuerStaff,
    IssuerStaffRequest,
    LearningPath,
    Network,
    NetworkInvite,
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
    IsStaff,
    MayEditBadgeClass,
    MayIssueBadgeClass,
    MayIssueLearningPath,
    is_learningpath_editor,
)
from issuer.serializers_v1 import (
    BadgeClassSerializerV1,
    BadgeInstanceSerializerV1,
    IssuerSerializerV1,
    IssuerStaffRequestSerializer,
    LearningPathParticipantSerializerV1,
    LearningPathSerializerV1,
    NetworkInviteSerializer,
    NetworkSerializerV1,
    QrCodeSerializerV1,
    RequestedBadgeSerializer,
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
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework import serializers, status
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
        return Issuer.objects.filter(staff__id=request.user.id).distinct()

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


class NetworkList(BaseEntityListView):
    """
    Network list resource for the authenticated user
    """

    model = Network
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
        # return self.request.user.cached_issuers()
        # Note: The issue with the commented line above is that When deleting an entity using the delete method,
        # it is removed from the database, but the cache is not invalidated. So this is a temporary workaround
        # till figuring out how to invalidate/refresh cache.
        # Force fresh data from the database
        return Network.objects.filter(staff__id=request.user.id).distinct()

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


class NetworkIssuerList(
    UncachedPaginatedViewMixin, VersionedObjectMixin, BaseEntityListView
):
    """
    GET a list of issuers within one network context
    """

    model = Network
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsEditor & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    v1_serializer_class = IssuerSerializerV1
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def get_queryset(self, request=None, **kwargs):
        network = self.get_object(request, **kwargs)
        return network.partner_issuers

    def get_context_data(self, **kwargs):
        context = super(NetworkIssuerList, self).get_context_data(**kwargs)
        context["network"] = self.get_object(self.request, **kwargs)
        return context

    @apispec_list_operation(
        "Issuer",
        summary="Get a list of issuers for a single Network",
        description="Authenticated user must have owner, editor, or staff status on the Network",
        tags=["Issuers", "Network"],
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
        return super(NetworkIssuerList, self).get(request, **kwargs)


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
            & MayIssueBadgeClass
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
        # verify the user has permission to the badgeclass
        self.get_object(request, **kwargs)
        return super(BadgeInstanceList, self).post(request, **kwargs)


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
                "activate_url": OriginSetting.HTTP
                + reverse(
                    "v1_api_user_confirm_staffrequest",
                    kwargs={"entity_id": staff_request.entity_id},
                ),
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
            network = Network.objects.get(entity_id=network_slug)
        except Network.DoesNotExist:
            return Response(
                {"response": "Network not found"}, status=status.HTTP_404_NOT_FOUND
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

        issuers = Issuer.objects.filter(entity_id__in=slugs)
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

        if existing_invitations.exists():
            pending_names = [inv.issuer.name for inv in existing_invitations]
            return Response(
                {
                    "response": f"Für diese Institutionen liegen bereits offene Einladungen vor: {', '.join(pending_names)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                            "v1_api_issuer_confirm_network_invite",
                            kwargs={
                                "networkSlug": network.entity_id,
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
                    {"detail": "Only pending invites can be confirmed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if invitation.status == NetworkInvite.Status.APPROVED:
                return Response(
                    {"detail": "Issuer is already a partner of this network"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                invitation.status = NetworkInvite.Status.APPROVED
                invitation.save()

                if invitation.issuer:
                    invitation.network.partner_issuers.add(invitation.issuer)

            serializer = self.v1_serializer_class(invitation)
            return Response(serializer.data)

        except NetworkInvite.DoesNotExist:
            return Response(
                {"detail": "Invitation not found"}, status=status.HTTP_404_NOT_FOUND
            )


class ConfirmNetworkInvitation(BaseEntityDetailView, BaseRedirectView):
    permission_classes = (permissions.AllowAny,)
    v1_serializer_class = BaseSerializer
    v2_serializer_class = BaseSerializerV2

    def get(self, request, **kwargs):
        """
        Redirect to frontend to confirm network invitation
        """
        badgrapp_id = request.query_params.get("a")
        badgrapp = BadgrApp.objects.get_by_id_or_default(badgrapp_id)
        networkSlug = kwargs.get("networkSlug")
        inviteSlug = kwargs.get("inviteSlug")
        intended_redirect = f"/issuer/networks/{networkSlug}/invite/{inviteSlug}"

        return self._prepare_redirect(request, badgrapp, intended_redirect)
