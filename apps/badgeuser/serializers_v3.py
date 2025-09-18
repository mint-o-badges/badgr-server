from rest_framework import serializers

from badgeuser.models import UserPreference


class PreferenceSerializerV3(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ["key", "value"]
