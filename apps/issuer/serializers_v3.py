from rest_framework import serializers
from entity.serializers import DetailSerializerV2
from issuer.models import BadgeClass


class BadgeClassSerializerV3(DetailSerializerV2):
    class Meta(DetailSerializerV2.Meta):
        model = BadgeClass


class BaseRequestIframeSerializer(serializers.Serializer):
    """Base serializer for all iFrame request endpoints"""

    LANGUAGES = [
        ("en", "English"),
        ("de", "German"),
    ]

    lang = serializers.ChoiceField(choices=LANGUAGES, default="en")


class RequestIframeSerializer(serializers.Serializer):
    email = serializers.CharField()


class RequestIframeBadgeProcessSerializer(BaseRequestIframeSerializer):
    issuer = serializers.CharField(allow_blank=True)
    badge = serializers.CharField(allow_blank=True)
