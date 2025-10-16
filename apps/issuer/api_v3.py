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
from rest_framework import viewsets, permissions
from rest_framework.response import Response

from apispec_drf.decorators import (
    apispec_list_operation,
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
from entity.api_v3 import EntityFilter, EntityViewSet, TagFilter

from .serializers_v1 import (
    BadgeClassSerializerV1,
    IssuerSerializerV1,
    LearningPathSerializerV1,
    NetworkSerializerV1,
)
from .models import BadgeClass, BadgeClassTag, BadgeInstance, Issuer, LearningPath


class BadgeFilter(EntityFilter):
    tags = TagFilter(field_name="badgeclasstag__name", lookup_expr="icontains")


class Badges(EntityViewSet):
    queryset = BadgeClass.objects.all()
    serializer_class = BadgeClassSerializerV1
    filterset_class = BadgeFilter
    ordering_fields = ["name", "created_at"]

    # only for apispec, get() does nothing on viewset
    @apispec_list_operation(
        "BadgeClass", summary="Get a list of Badges", tags=["BadgeClasses"]
    )
    def get(self, request, **kwargs):
        pass

    def get_queryset(self):
        print(self.request.user)
        queryset = super().get_queryset()
        return queryset.distinct()


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


class Issuers(EntityViewSet):
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


class Networks(EntityViewSet):
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


class LearningPaths(EntityViewSet):
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


class LearnersProfile(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):
        try:
            email = request.POST["email"]
        except KeyError:
            return HttpResponseBadRequest(b"Missing email parameter")

        if not request.user:
            return HttpResponseForbidden()

        issuers = Issuer.objects.filter(staff__id=request.user.id).distinct()
        if issuers.count == 0:
            return HttpResponseForbidden()

        instances = []
        for issuer in issuers:
            instances += BadgeInstance.objects.filter(
                issuer=issuer, recipient_identifier=email
            )

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        tree = get_skills_tree(instances, language)

        iframe = IframeUrl.objects.create(
            name="profile",
            params={"skills": tree["skills"], "language": language},
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})

class BadgeEdit(RequestIframe):
    permission_classes = [
        IsServerAdmin
        | (AuthenticatedWithVerifiedIdentifier & IsStaff & BadgrOAuthTokenHasScope)
        | BadgrOAuthTokenHasEntityScope
    ]
    valid_scopes = ["rw:issuer", "rw:issuer:*"]

    def post(self, request, **kwargs):

        try:
            language = request.POST["lang"]
            assert language in ["de", "en"]
        except (KeyError, AssertionError):
            language = "en"

        issuers = Issuer.objects.filter(staff__id=request.user.id).distinct()
        if issuers.count == 0:
            return HttpResponseForbidden()

        try:
            badge = request.POST["badge"]
        except KeyError:
            badge = ""
            pass


        if request.auth:
            application = request.auth.application
        else:
            # use public oauth app if not token auth
            application = Application.objects.get(client_type='public')

        # create short-lived oauth2 access token
        token = AccessToken.objects.create(
            user=request.user,
            application=application,
            token=random_token_generator(request, False),
            scope="rw:issuer",
            expires=(timezone.now() + timezone.timedelta(0, 3600))
        )

        iframe = IframeUrl.objects.create(
            name="badge-edit",
            params={"language": language, "token": token.token, "badge": badge},
            created_by=request.user,
        )

        return JsonResponse({"url": iframe.url})
