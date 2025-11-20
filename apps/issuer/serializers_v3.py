from collections import OrderedDict

import pytz

from apps.mainsite.serializers import DateTimeWithUtcZAtEndField
from entity.serializers import DetailSerializerV2
from issuer.models import BadgeClass, BadgeInstance, Issuer
from rest_framework import serializers


# only for apispec for now


class BadgeClassSerializerV3(DetailSerializerV2):
    class Meta(DetailSerializerV2.Meta):
        model = BadgeClass
