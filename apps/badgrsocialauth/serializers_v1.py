from mainsite.serializers import DateTimeWithUtcZAtEndField
from rest_framework import serializers


class BadgrSocialAccountSerializerV1(serializers.Serializer):
    id = serializers.CharField()
    provider = serializers.CharField()
    dateAdded = DateTimeWithUtcZAtEndField(source="date_joined")
    uid = serializers.CharField()

    def to_representation(self, instance):
        representation = super(BadgrSocialAccountSerializerV1, self).to_representation(
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

        representation.update(
            {
                "firstName": common_fields.get(
                    "first_name", common_fields.get("name", None)
                ),
                "lastName": common_fields.get("last_name", None),
                "primaryEmail": email,
                "url": url,
            }
        )

        return representation
