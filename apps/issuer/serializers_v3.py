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
        apispec_definition = (
            "BadgeClass",
            {
                "properties": OrderedDict(
                    [
                        (
                            "entityId",
                            {
                                "type": "string",
                                "format": "string",
                                "description": "Unique identifier for this BadgeClass",
                                "readOnly": True,
                            },
                        ),
                        (
                            "entityType",
                            {
                                "type": "string",
                                "format": "string",
                                "description": '"BadgeClass"',
                                "readOnly": True,
                            },
                        ),
                        (
                            "openBadgeId",
                            {
                                "type": "string",
                                "format": "url",
                                "description": "URL of the OpenBadge compliant json",
                                "readOnly": True,
                            },
                        ),
                        (
                            "createdAt",
                            {
                                "type": "string",
                                "format": "ISO8601 timestamp",
                                "description": "Timestamp when the BadgeClass was created",
                                "readOnly": True,
                            },
                        ),
                        (
                            "createdBy",
                            {
                                "type": "string",
                                "format": "entityId",
                                "description": "BadgeUser who created this BadgeClass",
                                "readOnly": True,
                            },
                        ),
                        (
                            "issuer",
                            {
                                "type": "string",
                                "format": "entityId",
                                "description": "entityId of the Issuer who owns the BadgeClass",
                                "required": False,
                            },
                        ),
                        (
                            "name",
                            {
                                "type": "string",
                                "format": "string",
                                "description": "Name of the BadgeClass",
                                "required": True,
                            },
                        ),
                        (
                            "description",
                            {
                                "type": "string",
                                "format": "string",
                                "description": "Short description of the BadgeClass",
                                "required": True,
                            },
                        ),
                        (
                            "image",
                            {
                                "type": "string",
                                "format": "data:image/png;base64",
                                "description": "Base64 encoded string of an image that represents the BadgeClass.",
                                "required": False,
                            },
                        ),
                        (
                            "criteriaUrl",
                            {
                                "type": "string",
                                "format": "url",
                                "description": (
                                    "External URL that describes in a human-readable "
                                    "format the criteria for the BadgeClass"
                                ),
                                "required": False,
                            },
                        ),
                        (
                            "criteriaNarrative",
                            {
                                "type": "string",
                                "format": "markdown",
                                "description": "Markdown formatted description of the criteria",
                                "required": False,
                            },
                        ),
                        (
                            "tags",
                            {
                                "type": "array",
                                "items": {"type": "string", "format": "string"},
                                "description": "List of tags that describe the BadgeClass",
                                "required": False,
                            },
                        ),
                        (
                            "alignments",
                            {
                                "type": "array",
                                "items": {"$ref": "#/definitions/BadgeClassAlignment"},
                                "description": "List of objects describing objectives or educational standards",
                                "required": False,
                            },
                        ),
                        (
                            "expires",
                            {
                                "$ref": "#/definitions/BadgeClassExpiration",
                                "description": "Expiration period for Assertions awarded from this BadgeClass",
                                "required": False,
                            },
                        ),
                    ]
                )
            },
        )


class BadgeClassMinimalSerializerV3(serializers.ModelSerializer):
    """Minimal BadgeClass info for nested display"""

    slug = serializers.CharField(source="entity_id", read_only=True)

    class Meta:
        model = BadgeClass
        fields = ["slug", "name", "image", "description"]
        read_only_fields = fields


class IssuerMinimalSerializerV3(serializers.ModelSerializer):
    """Minimal Issuer info for nested display"""

    slug = serializers.CharField(source="entity_id", read_only=True)

    class Meta:
        model = Issuer
        fields = ["slug", "name", "image"]
        read_only_fields = fields


class BadgeInstanceSerializerV3(serializers.ModelSerializer):
    slug = serializers.CharField(source="entity_id", read_only=True)
    created_at = DateTimeWithUtcZAtEndField(read_only=True, default_timezone=pytz.utc)
    issued_on = DateTimeWithUtcZAtEndField(
        source="created_at", read_only=True, default_timezone=pytz.utc
    )
    expires = DateTimeWithUtcZAtEndField(
        source="expires_at", read_only=True, allow_null=True, default_timezone=pytz.utc
    )

    badge_class = BadgeClassMinimalSerializerV3(source="badgeclass", read_only=True)
    issuer = IssuerMinimalSerializerV3(source="badgeclass.issuer", read_only=True)

    recipient_identifier = serializers.CharField(read_only=True)
    recipient_type = serializers.CharField(read_only=True)

    revoked = serializers.BooleanField(read_only=True)
    revocation_reason = serializers.CharField(read_only=True, allow_null=True)

    extensions = serializers.SerializerMethodField()

    public_url = serializers.SerializerMethodField()

    class Meta:
        model = BadgeInstance
        fields = [
            "slug",
            "created_at",
            "issued_on",
            "expires",
            "badge_class",
            "issuer",
            "recipient_identifier",
            "recipient_type",
            "revoked",
            "revocation_reason",
            "extensions",
            "public_url",
            "image",
            "narrative",
        ]
        read_only_fields = fields

    def get_extensions(self, obj):
        return obj.extension_items if hasattr(obj, "extension_items") else {}

    def get_public_url(self, obj):
        from mainsite.models import OriginSetting
        from django.urls import reverse

        return OriginSetting.HTTP + reverse(
            "badgeinstance_json", kwargs={"entity_id": obj.entity_id}
        )
