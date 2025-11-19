from entity.api_v3 import EntityViewSet
from backpack.serializers_v2 import BackpackAssertionSerializerV2
from issuer.permissions import (
    BadgrOAuthTokenHasScope,
    VerifiedEmailMatchesRecipientIdentifier,
)
from issuer.serializers_v1 import LearningPathSerializerV1
from issuer.models import BadgeInstance, LearningPath, LearningPathBadge
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class Badges(EntityViewSet):
    serializer_class = BackpackAssertionSerializerV2

    valid_scopes = {
        "get": ["r:backpack", "rw:backpack"],
        "post": ["rw:backpack"],
    }
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        VerifiedEmailMatchesRecipientIdentifier,
        BadgrOAuthTokenHasScope,
    )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BadgeInstance.objects.none()
        return self.request.user.cached_badgeinstances()


class LearningPaths(EntityViewSet):
    serializer_class = LearningPathSerializerV1

    valid_scopes = ["rw:backpack"]
    permission_classes = (
        AuthenticatedWithVerifiedIdentifier,
        VerifiedEmailMatchesRecipientIdentifier,
        BadgrOAuthTokenHasScope,
    )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LearningPath.objects.none()

        badgeinstances = self.request.user.cached_badgeinstances().all()
        badges = list({badgeinstance.badgeclass for badgeinstance in badgeinstances})
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(learningpathbadge__in=lp_badges).distinct()

        return lps

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="entity_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="The entity ID of the learning path",
            )
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
