from collections import OrderedDict

from entity.serializers import DetailSerializerV2
from issuer.models import BadgeClass


# only for apispec for now


class BadgeClassSerializerV3(DetailSerializerV2):
    class Meta(DetailSerializerV2.Meta):
        model = BadgeClass
