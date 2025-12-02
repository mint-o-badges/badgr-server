from django.conf import settings
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.utils import timezone
from django_filters import rest_framework as filters
from oauth2_provider.models import AccessToken, Application
from oauthlib.oauth2.rfc6749.tokens import random_token_generator
from rest_framework import viewsets, permissions, serializers
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import LimitOffsetPagination


from backpack.api import BackpackAssertionList
from badgeuser.api import LearningPathList
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiParameter,
)
from rest_framework.views import APIView

from backpack.utils import get_skills_tree
from mainsite.models import IframeUrl
from issuer.permissions import (
    BadgrOAuthTokenHasEntityScope,
    BadgrOAuthTokenHasScope,
    IsStaff,
)
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier, IsServerAdmin
from entity.api_v3 import (
    EntityFilter,
    EntityViewSet,
    TagFilter,
    TotalCountMixin,
)

from .serializers_v1 import (
    BadgeClassSerializerV1,
    BadgeInstanceSerializerV1,
    IssuerSerializerV1,
    LearningPathSerializerV1,
    NetworkSerializerV1,
)
from .models import (
    BadgeClass,
    BadgeClassTag,
    BadgeInstance,
    Issuer,
    LearningPath,
    BadgeInstanceExtension,
    LearningPathBadge,
)
from django.db.models import Q


class BadgeFilter(EntityFilter):
    tags = TagFilter(field_name="badgeclasstag__name", lookup_expr="icontains")


class BadgeInstanceV3FilterSet(filters.FilterSet):
    issuer = filters.CharFilter(field_name="issuer__entity_id", lookup_expr="exact")
    badgeclass = filters.CharFilter(
        field_name="badgeclass__entity_id", lookup_expr="exact"
    )
    recipient = filters.CharFilter(method="filter_recipient")

    def filter_recipient(self, queryset, name, value):
        if not value:
            return queryset

        matching_extensions = BadgeInstanceExtension.objects.filter(
            name="extensions:recipientProfile", original_json__icontains=value
        ).values_list("badgeinstance_id", flat=True)

        return queryset.filter(
            Q(recipient_identifier__icontains=value) | Q(pk__in=matching_extensions)
        ).distinct()

    class Meta:
        model = BadgeInstance
        fields = ["issuer", "badgeclass", "recipient"]


@extend_schema_view(
    list=extend_schema(
        summary="Get a list of Badges",
        tags=["BadgeClasses"],
        parameters=[
            OpenApiParameter(
                "tags",
                type=str,
                description="Filter by tag name (case-insensitive partial match)",
            ),
            OpenApiParameter(
                "ordering",
                type=str,
                description="Order by field. Available fields: name, created_at",
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get a specific Badge by ID",
        tags=["BadgeClasses"],
    ),
    create=extend_schema(
        summary="Create a new Badge",
        tags=["BadgeClasses"],
    ),
    update=extend_schema(
        summary="Update a Badge",
        tags=["BadgeClasses"],
    ),
    partial_update=extend_schema(
        summary="Partially update a Badge",
        tags=["BadgeClasses"],
    ),
    destroy=extend_schema(
        summary="Delete a Badge",
        tags=["BadgeClasses"],
    ),
)
class Badges(TotalCountMixin, EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1
    filterset_class = BadgeFilter
    ordering_fields = ["name", "created_at"]

    def get(self, request, **kwargs):
        pass

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.distinct()


class BadgeInstances(EntityViewSet, TotalCountMixin):
    queryset = BadgeInstance.objects.filter(revoked=False)
    serializer_class = BadgeInstanceSerializerV1
    pagination_class = LimitOffsetPagination
    filter_backends = [filters.DjangoFilterBackend, OrderingFilter]
    filterset_class = BadgeInstanceV3FilterSet
    ordering_fields = ["created_at", "recipient_identifier"]
    ordering = ["-created_at"]


@extend_schema_view(
    list=extend_schema(
        summary="Get a list of all available badge tags",
        tags=["BadgeClasses"],
        description="Fetch all available tags that existing Badges may be filtered by",
        responses={
            200: inline_serializer(
                name="BadgeTagsResponse",
                fields={"tags": serializers.ListField(child=serializers.CharField())},
            )
        },
    ),
)
class BadgeTags(viewsets.ViewSet):
    """A ViewSet to fetch all available tags the existing Badges may be filtered by"""

    permission_classes = [permissions.AllowAny]  # anybody may see all badge tags

    def list(self, request, **kwargs):
        tag_names = (
            BadgeClassTag.objects.order_by("name")
            .values_list("name", flat=True)
            .distinct()
        )
        return Response(list(tag_names))


@extend_schema_view(
    list=extend_schema(
        summary="Get a list of Issuers",
        tags=["Issuers"],
    ),
    retrieve=extend_schema(
        summary="Get a specific Issuer by ID",
        tags=["Issuers"],
    ),
    create=extend_schema(
        summary="Create a new Issuer",
        tags=["Issuers"],
    ),
    update=extend_schema(
        summary="Update an Issuer",
        tags=["Issuers"],
    ),
    partial_update=extend_schema(
        summary="Partially update an Issuer",
        tags=["Issuers"],
    ),
    destroy=extend_schema(
        summary="Delete an Issuer",
        tags=["Issuers"],
    ),
)
class Issuers(TotalCountMixin, EntityViewSet):
    queryset = Issuer.objects.all()
    serializer_class = IssuerSerializerV1

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # some fields have to be excluded due to data privacy concerns
        # in the get routes
        if self.request.method == "GET":
            context["exclude_fields"] = [
                *context.get("exclude_fields", []),
                "staff",
                "created_by",
            ]
        return context


@extend_schema_view(
    list=extend_schema(
        summary="Get a list of Networks",
        tags=["Networks"],
    ),
    retrieve=extend_schema(
        summary="Get a specific Network by ID",
        tags=["Networks"],
    ),
    create=extend_schema(
        summary="Create a new Network",
        tags=["Networks"],
    ),
    update=extend_schema(
        summary="Update a Network",
        tags=["Networks"],
    ),
    partial_update=extend_schema(
        summary="Partially update a Network",
        tags=["Networks"],
    ),
    destroy=extend_schema(
        summary="Delete a Network",
        tags=["Networks"],
    ),
)
class Networks(TotalCountMixin, EntityViewSet):
    queryset = Issuer.objects.filter(is_network=True)
    serializer_class = NetworkSerializerV1

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # some fields have to be excluded due to data privacy concerns
        # in the get routes
        if self.request.method == "GET":
            context["exclude_fields"] = [
                *context.get("exclude_fields", []),
                "staff",
                "created_by",
                "partner_issuers",
            ]
        return context


class LearningPathFilter(EntityFilter):
    tags = filters.CharFilter(
        field_name="learningpathtag__name", lookup_expr="icontains"
    )


@extend_schema_view(
    list=extend_schema(
        summary="Get a list of Learning Paths",
        tags=["LearningPaths"],
        parameters=[
            OpenApiParameter(
                "tags",
                type=str,
                description="Filter by tag name (case-insensitive partial match)",
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get a specific Learning Path by ID",
        tags=["LearningPaths"],
    ),
    create=extend_schema(
        summary="Create a new Learning Path",
        tags=["LearningPaths"],
    ),
    update=extend_schema(
        summary="Update a Learning Path",
        tags=["LearningPaths"],
    ),
    partial_update=extend_schema(
        summary="Partially update a Learning Path",
        tags=["LearningPaths"],
    ),
    destroy=extend_schema(
        summary="Delete a Learning Path",
        tags=["LearningPaths"],
    ),
)
class LearningPaths(TotalCountMixin, EntityViewSet):
    queryset = LearningPath.objects.all()
    serializer_class = LearningPathSerializerV1
    filterset_class = LearningPathFilter


class RequestIframe(APIView):
    # for easier in-browser testing
    def get(self, request, **kwargs):
        if settings.DEBUG:
            request._request.POST = request.GET
            return self.post(request, **kwargs)
        else:
            return HttpResponse(b"", status=405)

    def post(self, request, **kwargs):
        return HttpResponse()


def get_badgeinstances_from_post(request):
    try:
        email = request.POST["email"]
        emails = email.split(",")
    except KeyError:
        return HttpResponseBadRequest(b"Missing email parameter")

    issuers = Issuer.objects.filter(staff__id=request.user.id).distinct()
    if issuers.count == 0:
        return HttpResponseForbidden()

    instances = []
    for issuer in issuers:
        instances += BadgeInstance.objects.filter(
            issuer=issuer, recipient_identifier__in=emails
        )

    return instances


@extend_schema(exclude=True)
class LearnersProfile(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        if not request.user:
            return HttpResponseForbidden()

        instances = get_badgeinstances_from_post(request)

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        tree = get_skills_tree(
            BackpackAssertionList().get_filtered_objects(instances, True, False, True),
            language,
        )

        iframe = IframeUrl.objects.create(
            name="profile",
            params={"skills": tree["skills"], "language": language},
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class LearnersCompetencies(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        if not request.user:
            return HttpResponseForbidden()

        instances = get_badgeinstances_from_post(request)

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        badge_serializer = BackpackAssertionList.v1_serializer_class()
        badge_serializer.context["format"] = "plain"
        iframe = IframeUrl.objects.create(
            name="competencies",
            params={
                "badges": list(
                    badge_serializer.to_representation(i)
                    for i in BackpackAssertionList().get_filtered_objects(
                        instances, True, False, True
                    )
                ),
                "language": language,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class LearnersBadges(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        if not request.user:
            return HttpResponseForbidden()

        instances = get_badgeinstances_from_post(request)

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        badge_serializer = BackpackAssertionList.v1_serializer_class()
        badge_serializer.context["format"] = "plain"
        iframe = IframeUrl.objects.create(
            name="badges",
            params={
                "badges": list(
                    badge_serializer.to_representation(i)
                    for i in BackpackAssertionList().get_filtered_objects(
                        instances, True, False, True
                    )
                ),
                "language": language,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class LearnersLearningPaths(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        if not request.user:
            return HttpResponseForbidden()

        instances = get_badgeinstances_from_post(request)
        badges = list(
            {
                badgeinstance.badgeclass
                for badgeinstance in instances
                if badgeinstance.revoked is False
            }
        )
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(
            activated=True, learningpathbadge__in=lp_badges
        ).distinct()

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        iframe = IframeUrl.objects.create(
            name="learningpaths",
            params={
                "learningpaths": list(
                    LearningPathList.v1_serializer_class().to_representation(lp)
                    for lp in lps
                ),
                "language": language,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class LearnersBackpack(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        if not request.user:
            return HttpResponseForbidden()

        instances = get_badgeinstances_from_post(request)

        badges = list(
            {
                badgeinstance.badgeclass
                for badgeinstance in instances
                if badgeinstance.revoked is False
            }
        )
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(
            activated=True, learningpathbadge__in=lp_badges
        ).distinct()

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        filtered_instances = BackpackAssertionList().get_filtered_objects(
            instances, True, False, True
        )

        tree = get_skills_tree(filtered_instances, language)
        badge_serializer = BackpackAssertionList.v1_serializer_class()
        badge_serializer.context["format"] = "plain"
        iframe = IframeUrl.objects.create(
            name="backpack",
            params={
                "skills": tree["skills"],
                "badges": list(
                    badge_serializer.to_representation(i) for i in filtered_instances
                ),
                "learningpaths": list(
                    LearningPathList.v1_serializer_class().to_representation(lp)
                    for lp in lps
                ),
                "language": language,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class BadgeCreateEmbed(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*", "rw:profile"]

    def post(self, request, **kwargs):
        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        try:
            given_issuer = request.POST["issuer"]
            issuers = Issuer.objects.filter(staff__id=request.user.id).distinct()
            if (
                issuers.count() == 0
                or issuers.filter(entity_id=given_issuer).count() == 0
            ):
                return HttpResponseForbidden()
            issuer = issuers.get(entity_id=given_issuer)
        except KeyError:
            issuer = None
            pass

        if request.auth:
            application = request.auth.application
        else:
            # use public oauth app if not token auth
            application = Application.objects.get(client_type="public")

        # create short-lived oauth2 access token
        token = AccessToken.objects.create(
            user=request.user,
            application=application,
            token=random_token_generator(request, False),
            scope="rw:issuer rw:profile",
            expires=(timezone.now() + timezone.timedelta(0, 3600)),
        )

        iframe = IframeUrl.objects.create(
            name="badge-create-or-edit",
            params={
                "language": language,
                "token": token.token,
                "issuer": issuer.get_json() if issuer else None,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})


@extend_schema(exclude=True)
class BadgeEditEmbed(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*", "rw:profile"]

    def post(self, request, **kwargs):
        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        issuers = Issuer.objects.filter(staff__id=request.user.id).distinct()
        if issuers.count() == 0:
            return HttpResponseForbidden()

        try:
            badge_id = request.POST["badge"]
            badge = (
                BadgeClass.objects.filter(
                    entity_id=badge_id, issuer__staff__id=request.user.id
                )
                .distinct()
                .first()
            )
        except KeyError:
            badge = None

        if badge and not issuers.get(entity_id=badge.issuer.entity_id):
            return HttpResponseForbidden()

        if request.auth:
            application = request.auth.application
        else:
            # use public oauth app if not token auth
            application = Application.objects.get(client_type="public")

        # create short-lived oauth2 access token
        token = AccessToken.objects.create(
            user=request.user,
            application=application,
            token=random_token_generator(request, False),
            scope="rw:issuer rw:profile",
            expires=(timezone.now() + timezone.timedelta(0, 3600)),
        )

        iframe = IframeUrl.objects.create(
            name="badge-create-or-edit",
            params={
                "language": language,
                "token": token.token,
                "badge": BadgeClassSerializerV1(badge).data if badge else None,
                "issuer": badge.issuer.get_json() if badge else None,
                "badgeSelection": False if badge else True,
            },
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})
