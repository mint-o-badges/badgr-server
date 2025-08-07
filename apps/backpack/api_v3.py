from entity.api_v3 import EntityViewSet
from backpack.serializers_v2 import BackpackAssertionSerializerV2
from issuer.permissions import (
    BadgrOAuthTokenHasScope,
    VerifiedEmailMatchesRecipientIdentifier,
)
from issuer.serializers_v1 import LearningPathSerializerV1
from issuer.models import LearningPath, LearningPathBadge
from mainsite.permissions import AuthenticatedWithVerifiedIdentifier


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
        badgeinstances = self.request.user.cached_badgeinstances().all()
        badges = list({badgeinstance.badgeclass for badgeinstance in badgeinstances})
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(learningpathbadge__in=lp_badges).distinct()

        return lps
