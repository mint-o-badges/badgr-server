from entity.serializers import BaseSerializerV2, ListSerializerV2
from mainsite.serializers import DateTimeWithUtcZAtEndField
from rest_framework import serializers


class BadgrSocialAccountSerializerV2(BaseSerializerV2):
    id = serializers.CharField()
    provider = serializers.CharField()
    dateAdded = DateTimeWithUtcZAtEndField(source="date_joined")
    uid = serializers.CharField()

    class Meta:
        list_serializer_class = ListSerializerV2

    def to_representation(self, instance):
        representation = super(BadgrSocialAccountSerializerV2, self).to_representation(
            instance
        )

        try:
            provider = instance.get_provider()
            common_fields = provider.extract_common_fields(instance.extra_data)
        except AttributeError:
            # For SAML handling
            common_fields = dict()
            representation["id"] = instance.account_identifier
        email = common_fields.get("email", None)
        url = common_fields.get("url", None)
        if (
            not email
            and hasattr(instance, "extra_data")
            and "userPrincipalName" in instance.extra_data
        ):
            email = instance.extra_data["userPrincipalName"]

        if self.parent is None:
            result = representation["result"][0]
        else:
            result = representation

        result.update(
            {
                "firstName": common_fields.get("first_name", None),
                "lastName": common_fields.get("last_name", None),
                "primaryEmail": email,
                "url": url,
            }
        )

        return representation
