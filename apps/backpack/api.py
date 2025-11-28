# encoding: utf-8
from django.http import Http404, JsonResponse
from apps.backpack.utils import get_skills_tree
import logging
import datetime

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status

from backpack.models import (
    BackpackCollection,
    BackpackBadgeShare,
    BackpackCollectionShare,
)
from backpack.serializers_v1 import (
    CollectionSerializerV1,
    ImportedBadgeAssertionSerializer,
    LocalBadgeInstanceUploadSerializerV1,
)
from backpack.serializers_v2 import (
    BackpackAssertionSerializerV2,
    BackpackCollectionSerializerV2,
    BackpackImportSerializerV2,
    BackpackAssertionAcceptanceSerializerV2,
)
from entity.api import BaseEntityListView, BaseEntityDetailView
from issuer.models import BadgeInstance, ImportedBadgeAssertion
from issuer.permissions import (
    AuditedModelOwner,
    VerifiedEmailMatchesRecipientIdentifier,
    BadgrOAuthTokenHasScope,
)
from issuer.public_api import ImagePropertyDetailView
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiTypes,
    inline_serializer,
)
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier, IsServerAdmin

from badgeuser.models import BadgeUser

logger = logging.getLogger("Badgr.Events")

_TRUE_VALUES = ["true", "t", "on", "yes", "y", "1", 1, 1.0, True]
_FALSE_VALUES = ["false", "f", "off", "no", "n", "0", 0, 0.0, False]


def _scrub_boolean(boolean_str, default=None):
    if boolean_str in _TRUE_VALUES:
        return True
    if boolean_str in _FALSE_VALUES:
        return False
    return default


@extend_schema_view(
    get=extend_schema(
        summary="List imported badge assertions",
        description="Get a list of all imported badge assertions for the authenticated user",
        tags=["Backpack"],
        responses={200: ImportedBadgeAssertionSerializer(many=True)},
    ),
    post=extend_schema(
        summary="Import a new badge assertion",
        description="Create a new imported badge instance",
        tags=["Backpack"],
        request=ImportedBadgeAssertionSerializer,
        responses={201: ImportedBadgeAssertionSerializer},
    ),
)
class ImportedBadgeInstanceList(BaseEntityListView):
    """
    API endpoint for importing and listing imported badge assertions
    """

    model = ImportedBadgeAssertion
    v1_serializer_class = ImportedBadgeAssertionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ("get", "post")

    def get_objects(self, request, **kwargs):
        return ImportedBadgeAssertion.objects.filter(user=self.request.user)

    def get_queryset(self):
        """Filter imported badges to the current user"""
        return ImportedBadgeAssertion.objects.filter(user=self.request.user)

    def post(self, request, **kwargs):
        """Create a new imported badge instance"""
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.validated_data["user"] = request.user
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(
        summary="Get an imported badge assertion",
        description="Retrieve details of a specific imported badge",
        tags=["Backpack"],
        responses={200: ImportedBadgeAssertionSerializer},
    ),
    delete=extend_schema(
        summary="Delete an imported badge",
        description="Remove an imported badge from the backpack",
        tags=["Backpack"],
        responses={204: None},
    ),
)
class ImportedBadgeInstanceDetail(BaseEntityDetailView):
    """
    API endpoint for retrieving, updating, or deleting an imported badge
    """

    model = ImportedBadgeAssertion
    v1_serializer_class = ImportedBadgeAssertionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self, request, **kwargs):
        entity_id = kwargs.get("entity_id")
        try:
            return ImportedBadgeAssertion.objects.get(entity_id=entity_id)
        except ImportedBadgeAssertion.DoesNotExist:
            raise Http404

    def get_queryset(self):
        """Filter imported badges to the current user"""
        return ImportedBadgeAssertion.objects.filter(user=self.request.user)

    def delete(self, request, **kwargs):
        """Delete an imported badge from the backpack"""
        badge = self.get_object(request, **kwargs)
        badge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        operation_id="earner_badges_list",
        summary="Get a list of Assertions in authenticated user's backpack",
        description="Retrieve all badge assertions from the authenticated user's backpack",
        tags=["Backpack"],
        parameters=[
            OpenApiParameter(
                name="include_expired",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include expired badges (default: true for v1, false for v2)",
            ),
            OpenApiParameter(
                name="include_revoked",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include revoked badges (default: false)",
            ),
            OpenApiParameter(
                name="include_pending",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include pending badges (default: false)",
            ),
            OpenApiParameter(
                name="expand",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Expand related objects (badgeclass, issuer)",
                many=True,
            ),
        ],
    ),
    post=extend_schema(
        operation_id="earner_badges_upload",
        summary="Upload a new Assertion to the backpack",
        description="Upload a new badge assertion to the user's backpack",
        tags=["Backpack"],
    ),
)
class BackpackAssertionList(BaseEntityListView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        VerifiedEmailMatchesRecipientIdentifier,
        BadgrOAuthTokenHasScope,
    )
    http_method_names = ("get", "post")
    valid_scopes = {
        "get": ["r:backpack", "rw:backpack"],
        "post": ["rw:backpack"],
    }
    include_defaults = {
        "include_expired": {"v1": "true", "v2": "false"},
        "include_revoked": {"v1": "false", "v2": "false"},
        "include_pending": {"v1": "false", "v2": "false"},
    }

    def get_filtered_objects(
        self, instances, include_expired, include_revoked, include_pending
    ):
        def badge_filter(b):
            if (
                (b.acceptance == BadgeInstance.ACCEPTANCE_REJECTED)
                or (
                    not include_expired
                    and b.expires_at is not None
                    and b.expires_at < timezone.now()
                )
                or (not include_revoked and b.revoked)
                or (not include_pending and b.pending)
            ):
                return False
            return True

        return list(filter(badge_filter, instances))

    def get_objects(self, request, **kwargs):
        version = kwargs.get("version", "v1")
        include_expired = request.query_params.get(
            "include_expired", self.include_defaults["include_expired"][version]
        ).lower() in ["1", "true"]
        include_revoked = request.query_params.get(
            "include_revoked", self.include_defaults["include_revoked"][version]
        ).lower() in ["1", "true"]
        include_pending = request.query_params.get(
            "include_pending", self.include_defaults["include_pending"][version]
        ).lower() in ["1", "true"]

        return self.get_filtered_objects(
            self.request.user.cached_badgeinstances(),
            include_expired,
            include_revoked,
            include_pending,
        )

    def get(self, request, **kwargs):
        mykwargs = kwargs.copy()
        mykwargs["expands"] = []
        expands = request.GET.getlist("expand", [])

        if "badgeclass" in expands:
            mykwargs["expands"].append("badgeclass")
        if "issuer" in expands:
            mykwargs["expands"].append("issuer")

        return super(BackpackAssertionList, self).get(request, **mykwargs)

    def post(self, request, **kwargs):
        if kwargs.get("version", "v1") == "v1":
            try:
                return super(BackpackAssertionList, self).post(request, **kwargs)
            except serializers.ValidationError as e:
                self.log_not_created(e)
                raise e
        raise NotImplementedError("use BackpackImportBadge.post instead")

    def log_not_created(self, error):
        request = self.request
        user = request.user
        image_data = ""
        user_entity_id = ""
        error_name = ""
        error_result = ""

        if request.data.get("image", None) is not None:
            image_data = request.data.get("image", "")[:1024]

        if user is not None:
            user_entity_id = user.entity_id

        if len(error.detail) <= 1:
            # grab first error
            e = error.detail[0]
            error_name = e.get("name", "")
            error_result = e.get("result", "")

        logger.warning(
            "Invalid badge uploaded. Image data: '%s'; user_entity_id: '%s'; error_name: '%s'; error_result: '%s'",
            image_data,
            user_entity_id,
            error_name,
            error_result,
        )

    def get_context_data(self, **kwargs):
        context = super(BackpackAssertionList, self).get_context_data(**kwargs)
        context["format"] = self.request.query_params.get(
            "json_format", "v1"
        )  # for /v1/earner/badges compat
        return context


@extend_schema_view(
    get=extend_schema(
        operation_id="earner_badge_retrieve",
        summary="Get detail on an Assertion in the user's Backpack",
        description="Retrieve detailed information about a specific badge assertion",
        tags=["Backpack"],
        parameters=[
            OpenApiParameter(
                name="expand",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Expand related objects (badgeclass, issuer)",
                many=True,
            ),
        ],
    ),
    delete=extend_schema(
        operation_id="earner_badge_delete",
        summary="Remove an assertion from the backpack",
        description="Delete a badge assertion from the user's backpack",
        tags=["Backpack"],
        responses={204: None},
    ),
    put=extend_schema(
        operation_id="earner_badge_update_acceptance",
        summary="Update acceptance of an Assertion in the user's Backpack",
        description="Update the acceptance status of a badge assertion",
        tags=["Backpack"],
        request=BackpackAssertionAcceptanceSerializerV2,
        responses={200: BackpackAssertionSerializerV2},
    ),
)
class BackpackAssertionDetail(BaseEntityDetailView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        VerifiedEmailMatchesRecipientIdentifier,
        BadgrOAuthTokenHasScope,
    )
    http_method_names = ("get", "delete", "put")
    valid_scopes = {
        "get": ["r:backpack", "rw:backpack"],
        "put": ["rw:backpack"],
        "delete": ["rw:backpack"],
    }

    def get_context_data(self, **kwargs):
        context = super(BackpackAssertionDetail, self).get_context_data(**kwargs)
        context["format"] = self.request.query_params.get(
            "json_format", "v1"
        )  # for /v1/earner/badges compat
        return context

    def get(self, request, **kwargs):
        mykwargs = kwargs.copy()
        mykwargs["expands"] = []
        expands = request.GET.getlist("expand", [])

        if "badgeclass" in expands:
            mykwargs["expands"].append("badgeclass")
        if "issuer" in expands:
            mykwargs["expands"].append("issuer")

        return super(BackpackAssertionDetail, self).get(request, **mykwargs)

    def delete(self, request, **kwargs):
        obj = self.get_object(request, **kwargs)
        related_collections = list(
            BackpackCollection.objects.filter(
                backpackcollectionbadgeinstance__badgeinstance=obj
            )
        )

        if obj.source_url is None:
            obj.acceptance = BadgeInstance.ACCEPTANCE_REJECTED
            obj.save()
        else:
            obj.delete()

        for collection in related_collections:
            collection.save()

        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request, **kwargs):
        fields_whitelist = ("acceptance",)
        data = {k: v for k, v in list(request.data.items()) if k in fields_whitelist}

        obj = self.get_object(request, **kwargs)
        if not self.has_object_permissions(request, obj):
            return Response(status=status.HTTP_404_NOT_FOUND)

        context = self.get_context_data(**kwargs)

        update_serializer = BackpackAssertionAcceptanceSerializerV2(
            obj, data, context=context
        )
        update_serializer.is_valid(raise_exception=True)
        update_serializer.save(updated_by=request.user)

        main_serializer_class = self.get_serializer_class()
        serializer = main_serializer_class(update_serializer.instance, context=context)

        return Response(serializer.data)


@extend_schema(exclude=True)
class BackpackAssertionDetailImage(ImagePropertyDetailView, BadgrOAuthTokenHasScope):
    model = BadgeInstance
    prop = "image"
    valid_scopes = ["r:backpack", "rw:backpack"]


@extend_schema(
    summary="Get skills tree from backpack assertions",
    description="Retrieve a hierarchical skills tree from the user's badge assertions",
    tags=["Backpack"],
    parameters=[
        OpenApiParameter(
            name="lang",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Language for skills (de or en, default: de)",
            enum=["de", "en"],
        ),
    ],
    responses={200: OpenApiTypes.OBJECT},
)
class BackpackSkillList(BackpackAssertionList):
    def get(self, request, **kwargs):
        instances = self.get_objects(request)
        if not instances:
            return JsonResponse({"skills": []})

        try:
            lang = request.query_params.get("lang")
            assert lang == "de" or lang == "en"
        except Exception:
            lang = "de"

        skills = get_skills_tree(instances, lang)

        return JsonResponse(skills)


@extend_schema(
    summary="Get a list of Badges from a specific user",
    description="Retrieve all badges for a user specified by email (admin only)",
    tags=["Backpack"],
    parameters=[
        OpenApiParameter(
            name="email",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description="Email address of the user",
            required=True,
        ),
    ],
)
class BadgesFromUser(BaseEntityListView):
    model = BadgeInstance
    v1_serializer_class = LocalBadgeInstanceUploadSerializerV1
    v2_serializer_class = BackpackAssertionSerializerV2
    permission_classes = (IsServerAdmin,)
    valid_scopes = {
        "get": ["rw:serverAdmin"],
    }

    def get_objects(self, request, **kwargs):
        email = kwargs.get("email")
        try:
            user = BadgeUser.cached.get(email=email)
            return list(user.get_badges_from_user())
        except BadgeUser.DoesNotExist:
            raise ValueError("User not found")

    def get(self, request, **kwargs):
        return super(BadgesFromUser, self).get(request, **kwargs)


@extend_schema_view(
    get=extend_schema(
        operation_id="earner_collection_list",
        summary="Get a list of Collections",
        description="Retrieve all badge collections for the authenticated user",
        tags=["Backpack"],
        responses={200: BackpackCollectionSerializerV2(many=True)},
    ),
    post=extend_schema(
        operation_id="earner_collection_add",
        summary="Create a new Collection",
        description="Create a new badge collection",
        tags=["Backpack"],
        request=BackpackCollectionSerializerV2,
        responses={201: BackpackCollectionSerializerV2},
    ),
)
class BackpackCollectionList(BaseEntityListView):
    model = BackpackCollection
    v1_serializer_class = CollectionSerializerV1
    v2_serializer_class = BackpackCollectionSerializerV2
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        AuditedModelOwner,
        BadgrOAuthTokenHasScope,
    )
    valid_scopes = {
        "get": ["r:backpack", "rw:backpack"],
        "post": ["rw:backpack"],
    }

    def get_objects(self, request, **kwargs):
        return self.request.user.cached_backpackcollections()

    def get(self, request, **kwargs):
        return super(BackpackCollectionList, self).get(request, **kwargs)

    def post(self, request, **kwargs):
        return super(BackpackCollectionList, self).post(request, **kwargs)


@extend_schema_view(
    get=extend_schema(
        operation_id="earner_collection_retrieve",
        summary="Get a single Collection",
        description="Retrieve details of a specific badge collection",
        tags=["Backpack"],
        responses={200: BackpackCollectionSerializerV2},
    ),
    put=extend_schema(
        operation_id="earner_collection_update",
        summary="Update a Collection",
        description="Update an existing badge collection",
        tags=["Backpack"],
        request=BackpackCollectionSerializerV2,
        responses={200: BackpackCollectionSerializerV2},
    ),
    delete=extend_schema(
        summary="Delete a collection",
        description="Remove a badge collection",
        tags=["Backpack"],
        responses={204: None},
    ),
)
class BackpackCollectionDetail(BaseEntityDetailView):
    model = BackpackCollection
    v1_serializer_class = CollectionSerializerV1
    v2_serializer_class = BackpackCollectionSerializerV2
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        AuditedModelOwner,
        BadgrOAuthTokenHasScope,
    )
    valid_scopes = {
        "get": ["r:backpack", "rw:backpack"],
        "post": ["rw:backpack"],
        "put": ["rw:backpack"],
        "delete": ["rw:backpack"],
    }

    def get(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).get(request, **kwargs)

    def put(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).put(request, **kwargs)

    def delete(self, request, **kwargs):
        return super(BackpackCollectionDetail, self).delete(request, **kwargs)


@extend_schema(
    summary="Import a new Assertion to the backpack",
    description="Import a badge assertion from URL, image, or JSON",
    tags=["Backpack"],
    request=inline_serializer(
        name="BackpackImportRequest",
        fields={
            "url": serializers.URLField(
                required=False,
                help_text="URL to an OpenBadge compliant badge",
            ),
            "image": serializers.CharField(
                required=False,
                help_text="Base64 encoded Baked OpenBadge image (data:image/png;base64,...)",
            ),
            "assertion": serializers.JSONField(
                required=False,
                help_text="OpenBadge compliant JSON",
            ),
        },
    ),
    responses={201: BackpackAssertionSerializerV2},
)
class BackpackImportBadge(BaseEntityListView):
    v2_serializer_class = BackpackImportSerializerV2
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        BadgrOAuthTokenHasScope,
    )
    http_method_names = ("post",)
    valid_scopes = ["rw:backpack"]

    def post(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        new_instance = serializer.save(created_by=request.user)
        self.log_create(new_instance)

        response_serializer = BackpackAssertionSerializerV2(
            new_instance, context=context
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Share a badge assertion",
    description="Share a single badge to a supported share provider (Facebook, LinkedIn)",
    tags=["Backpack"],
    parameters=[
        OpenApiParameter(
            name="provider",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="The share provider (facebook, linkedin)",
            required=True,
            enum=["facebook", "linkedin"],
        ),
        OpenApiParameter(
            name="redirect",
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description="Whether to redirect to the share URL (default: true)",
        ),
        OpenApiParameter(
            name="source",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Source of the share action",
        ),
        OpenApiParameter(
            name="include_identifier",
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description="Include recipient identifier in share",
        ),
    ],
    responses={
        302: OpenApiTypes.OBJECT,
        200: inline_serializer(
            name="ShareResponse",
            fields={"url": serializers.URLField()},
        ),
    },
)
class ShareBackpackAssertion(BaseEntityDetailView):
    model = BadgeInstance
    permission_classes = (
        permissions.AllowAny,
    )  # this is AllowAny to support tracking sharing links in emails
    http_method_names = ("get",)
    allow_any_unauthenticated_access = True

    def get(self, request, **kwargs):
        """Share a single badge to a support share provider"""
        redirect = _scrub_boolean(request.query_params.get("redirect", "1"))

        provider = request.query_params.get("provider")
        if not provider:
            return Response(
                {"error": "unspecified share provider"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provider = provider.lower()

        source = request.query_params.get("source", "unknown")

        badge = self.get_object(request, **kwargs)
        if not badge:
            return Response(status=status.HTTP_404_NOT_FOUND)

        include_identifier = _scrub_boolean(
            request.query_params.get("include_identifier", False)
        )

        share = BackpackBadgeShare(
            provider=provider, badgeinstance=badge, source=source
        )
        share_url = share.get_share_url(provider, include_identifier=include_identifier)
        if not share_url:
            return Response(
                {"error": "invalid share provider"}, status=status.HTTP_400_BAD_REQUEST
            )

        share.save()
        logger.info(
            "Badge '%s' shared by '%s' at '%s' from '%s'",
            badge.entity_id,
            provider,
            datetime.datetime.now(),
            source,
        )

        if redirect:
            headers = {"Location": share_url}
            return Response(status=status.HTTP_302_FOUND, headers=headers)
        else:
            return Response({"url": share_url})


@extend_schema(
    summary="Share a badge collection",
    description="Share a collection to a supported share provider (Facebook, LinkedIn)",
    tags=["Backpack"],
    parameters=[
        OpenApiParameter(
            name="provider",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="The share provider (facebook, linkedin)",
            required=True,
            enum=["facebook", "linkedin"],
        ),
        OpenApiParameter(
            name="redirect",
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description="Whether to redirect to the share URL (default: true)",
        ),
        OpenApiParameter(
            name="source",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Source of the share action",
        ),
    ],
    responses={
        302: OpenApiTypes.OBJECT,
        200: inline_serializer(
            name="ShareCollectionResponse",
            fields={"url": serializers.URLField()},
        ),
    },
)
class ShareBackpackCollection(BaseEntityDetailView):
    model = BackpackCollection
    permission_classes = (
        permissions.AllowAny,
    )  # this is AllowAny to support tracking sharing links in emails
    http_method_names = ("get",)

    def get(self, request, **kwargs):
        """Share a collection to a supported share provider"""
        redirect = _scrub_boolean(request.query_params.get("redirect", "1"))

        provider = request.query_params.get("provider")
        if not provider:
            return Response(
                {"error": "unspecified share provider"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provider = provider.lower()

        source = request.query_params.get("source", "unknown")

        collection = self.get_object(request, **kwargs)
        if not collection:
            return Response(status=status.HTTP_404_NOT_FOUND)

        share = BackpackCollectionShare(
            provider=provider, collection=collection, source=source
        )
        share_url = share.get_share_url(
            provider, title=collection.name, summary=collection.description
        )
        if not share_url:
            return Response(
                {"error": "invalid share provider"}, status=status.HTTP_400_BAD_REQUEST
            )

        share.save()

        if redirect:
            headers = {"Location": share_url}
            return Response(status=status.HTTP_302_FOUND, headers=headers)
        else:
            return Response({"url": share_url})
