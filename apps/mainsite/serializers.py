import json
from collections import OrderedDict

import logging
logger = logging.getLogger("Badgr.Events")
import pytz
from django.utils.html import strip_tags
from entity.serializers import BaseSerializerV2
from mainsite.pagination import BadgrCursorPagination
from rest_framework import serializers
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.exceptions import ValidationError


class HumanReadableBooleanField(serializers.BooleanField):
    TRUE_VALUES = serializers.BooleanField.TRUE_VALUES | set(("on", "On", "ON"))
    TRUE_VALUES = serializers.BooleanField.TRUE_VALUES | set(("on", "On", "ON"))
    FALSE_VALUES = serializers.BooleanField.FALSE_VALUES | set(("off", "Off", "OFF"))


class ReadOnlyJSONField(serializers.CharField):
    def to_representation(self, value):
        if isinstance(value, (dict, list)):
            return value
        else:
            raise serializers.ValidationError(
                "WriteableJsonField: Did not get a JSON-serializable datatype "
                "from storage for this item: " + str(value)
            )


class WritableJSONField(ReadOnlyJSONField):
    def to_internal_value(self, data):
        try:
            internal_value = json.loads(data)
        except Exception:
            # TODO: this is going to choke on dict input, when it should be allowed in addition to JSON.
            raise serializers.ValidationError(
                "WriteableJsonField: Could not process input into a python dict for storage "
                + str(data)
            )

        return internal_value


class LinkedDataEntitySerializer(serializers.Serializer):
    def to_representation(self, instance):
        representation = super(LinkedDataEntitySerializer, self).to_representation(
            instance
        )
        representation["@id"] = instance.jsonld_id

        try:
            representation["@type"] = self.jsonld_type
        except AttributeError:
            pass

        return representation


class LinkedDataReferenceField(serializers.Serializer):
    """
    A read-only field for embedding representations of entities that have Linked Data identifiers.
    Includes their @id by default and any additional identifier keys that are the named
    properties on the instance.
    """

    def __init__(self, keys=[], model=None, read_only=True, field_names=None, **kwargs):
        kwargs.pop("many", None)
        super(LinkedDataReferenceField, self).__init__(read_only=read_only, **kwargs)
        self.included_keys = keys
        self.model = model
        self.field_names = field_names

    def to_representation(self, obj):
        output = OrderedDict()
        output["@id"] = obj.jsonld_id

        for key in self.included_keys:
            field_name = key
            if self.field_names is not None and key in self.field_names:
                field_name = self.field_names.get(key)
            output[key] = getattr(obj, field_name, None)

        return output

    def to_internal_value(self, data):
        if not isinstance(data, str):
            idstring = data.get("@id")
        else:
            idstring = data

        try:
            return self.model.cached.get_by_id(idstring)
        except AttributeError:
            raise TypeError(
                "LinkedDataReferenceField model must be declared and use cache "
                + "manager that implements get_by_id method."
            )


class LinkedDataReferenceList(serializers.ListField):
    # child must be declared in implementation.
    def get_value(self, dictionary):
        try:
            return dictionary.getlist(self.field_name, serializers.empty)
        except AttributeError:
            return dictionary.get(self.field_name, serializers.empty)


class JSONDictField(serializers.DictField):
    """
    A DictField that also accepts JSON strings as input
    """

    def to_internal_value(self, data):
        try:
            data = json.loads(data)
        except TypeError:
            pass

        return super(JSONDictField, self).to_internal_value(data)


class CachedUrlHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):
    def get_url(self, obj, view_name, request, format):
        """
        The value of this field is driven by a source argument that returns the actual URL,
        so no need to reverse it from a value.
        """
        return obj


class StripTagsCharField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        self.strip_tags = kwargs.pop("strip_tags", True)
        self.convert_null = kwargs.pop(
            "convert_null", False
        )  # Converts db nullable fields to empty strings
        super(StripTagsCharField, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):
        value = super(StripTagsCharField, self).to_internal_value(data)
        if self.strip_tags:
            return strip_tags(value)
        return value

    def get_attribute(self, instance):
        value = super(StripTagsCharField, self).get_attribute(instance)
        if self.convert_null:
            return value if value is not None else ""
        return value


class MarkdownCharFieldValidator(object):
    def __call__(self, value):
        if "![" in value:
            raise ValidationError("Images not supported in markdown")


class MarkdownCharField(StripTagsCharField):
    default_validators = []


class LegacyVerifiedAuthTokenSerializer(AuthTokenSerializer):
    def validate(self, attrs):
        attrs = super(LegacyVerifiedAuthTokenSerializer, self).validate(attrs)
        user = attrs.get("user")

        logger.warning("Deprecated new auth token")
        logger.info("Username: '%s'", user.username)
        if not user.verified:
            try:
                email = user.cached_emails()[0]
                email.send_confirmation()
            except IndexError:
                pass
            raise ValidationError(
                "You must verify your primary email address before you can sign in."
            )
        return attrs


class OriginalJsonSerializerMixin(serializers.Serializer):
    def to_representation(self, instance):
        representation = super(OriginalJsonSerializerMixin, self).to_representation(
            instance
        )

        if hasattr(instance, "get_filtered_json"):
            # properties in original_json not natively supported
            extra_properties = instance.get_filtered_json()
            if extra_properties and len(extra_properties) > 0:
                for k, v in list(extra_properties.items()):
                    if (
                        k not in representation
                        or v is not None
                        and representation.get(k, None) is None
                    ):
                        representation[k] = v

        return representation


class ExcludeFieldsMixin:
    """
    A mixin to recursively exclude specific fields from the given request data.

    Use in a serializers `get_fields` method to enable it:
    ```
    def get_fields(self):
        fields = super().get_fields()
        ...
        # Use the mixin to exclude any fields that are unwantend in the final result
        exclude_fields = self.context.get("exclude_fields", [])
        self.exclude_fields(fields, exclude_fields)
        return fields
    ```

    Then use the context of the serializer to enable it:
    ```
    context["exclude_fields"] = [
        *context.get("exclude_fields", []),
        "staff",
        "created_by",
    ]
    ```

    You can also hook into the `to_representation` method
    to exclude fields from the final json (e.g. when extensions are present)
    instead of using the get_fields method:
    ```
    def to_representation(self, instance):
        representation = super(BadgeClassSerializerV1, self).to_representation(instance)
        exclude_fields = self.context.get("exclude_fields", [])
        self.exclude_fields(representation, exclude_fields)
        ...
        return representation
    ```
    """

    def exclude_fields(self, data, fields_to_exclude):
        """
        Exclude specified fields from the given request data recusively.
        """
        for field in fields_to_exclude:
            if isinstance(data, dict):
                data.pop(field, None)
                for key in data.keys():
                    data[key] = self.exclude_fields(data[key], [field])
            elif isinstance(data, list):
                for item in data:
                    self.exclude_fields(item, [field])

        return data


class CursorPaginatedListSerializer(serializers.ListSerializer):
    def __init__(self, queryset, request, ordering="updated_at", *args, **kwargs):
        self.paginator = BadgrCursorPagination(ordering=ordering)
        self.page = self.paginator.paginate_queryset(queryset, request)
        super(CursorPaginatedListSerializer, self).__init__(
            data=self.page, *args, **kwargs
        )

    def to_representation(self, data):
        representation = super(CursorPaginatedListSerializer, self).to_representation(
            data
        )
        envelope = BaseSerializerV2.response_envelope(
            result=representation, success=True, description="ok"
        )
        envelope["pagination"] = self.paginator.get_page_info()
        return envelope

    @property
    def data(self):
        return super(serializers.ListSerializer, self).data


class DateTimeWithUtcZAtEndField(serializers.DateTimeField):
    timezone = pytz.utc


class ApplicationInfoSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True, source="get_visible_name")
    image = serializers.URLField(read_only=True, source="get_icon_url")
    website_url = serializers.URLField(read_only=True)
    clientId = serializers.CharField(read_only=True, source="application.client_id")
    policyUri = serializers.URLField(read_only=True, source="policy_uri")
    termsUri = serializers.URLField(read_only=True, source="terms_uri")


class AuthorizationSerializer(serializers.Serializer):
    client_id = serializers.CharField(required=True)
    redirect_uri = serializers.URLField(required=True)
    response_type = serializers.CharField(required=False, default=None, allow_null=True)
    state = serializers.CharField(required=False, default=None, allow_null=True)
    scopes = serializers.ListField(child=serializers.CharField())
    scope = serializers.CharField(required=False, default=None, allow_null=True)
    allow = serializers.BooleanField(required=True)
    code_challenge = serializers.CharField(required=False)
    code_challenge_method = serializers.CharField(required=False)
