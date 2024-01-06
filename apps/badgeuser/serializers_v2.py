from collections import OrderedDict

from rest_framework import serializers
from django.contrib.auth.hashers import is_password_usable

from badgeuser.models import BadgeUser, TermsVersion
from badgeuser.utils import notify_on_password_change
from entity.serializers import DetailSerializerV2, BaseSerializerV2, ListSerializerV2
from mainsite.models import BadgrApp
from mainsite.serializers import ApplicationInfoSerializer, DateTimeWithUtcZAtEndField, StripTagsCharField
from mainsite.validators import PasswordValidator


class BadgeUserEmailSerializerV2(DetailSerializerV2):
    email = serializers.EmailField()
    verified = serializers.BooleanField(read_only=True)
    primary = serializers.BooleanField(required=False, default=False)
    caseVariants = serializers.ListField(child=serializers.CharField(), required=False, source='cached_variant_emails')

    class Meta(DetailSerializerV2.Meta):
        apispec_definition = ('BadgeUserEmail', {
            'properties': OrderedDict([
                ('email', {
                    'type': "string",
                    'format': "email",
                    'description': "Email address associated with a BadgeUser",
                }),
                ('verified', {
                    'type': "boolean",
                    'description': "True if the email address has been verified",
                }),
                ('primary', {
                    'type': "boolean",
                    'description': "True for a single email address to receive email notifications",
                }),
            ])
        })


class BadgeUserSerializerV2(DetailSerializerV2):
    firstName = StripTagsCharField(source='first_name', max_length=30, allow_blank=True)
    lastName = StripTagsCharField(source='last_name', max_length=150, allow_blank=True)
    password = serializers.CharField(style={'input_type': 'password'},
            write_only=True, required=False, validators=[PasswordValidator()])
    currentPassword = serializers.CharField(style={'input_type': 'password'},
            write_only=True, required=False)
    emails = BadgeUserEmailSerializerV2(many=True, source='email_items', required=False)
    url = serializers.ListField(read_only=True, source='cached_verified_urls')
    telephone = serializers.ListField(read_only=True, source='cached_verified_phone_numbers')
    agreedTermsVersion = serializers.IntegerField(source='agreed_terms_version', required=False)
    hasAgreedToLatestTermsVersion = serializers.SerializerMethodField(read_only=True)
    marketingOptIn = serializers.BooleanField(source='marketing_opt_in', required=False)
    badgrDomain = serializers.CharField(read_only=True, max_length=255, source='badgrapp')
    hasPasswordSet = serializers.SerializerMethodField('get_has_password_set')
    recipient = serializers.SerializerMethodField(read_only=True)

    def get_has_password_set(self, obj):
        return is_password_usable(obj.password)

    def get_recipient(self, obj):
        primary_email = next((e for e in obj.cached_emails() if e.primary), None)
        if primary_email:
            return dict(type='email', identity=primary_email.email)
        identifier = obj.userrecipientidentifier_set.filter(verified=True).order_by('pk').first()
        if identifier:
            return dict(type=identifier.type, identity=identifier.identifier)
        return None

    def get_hasAgreedToLatestTermsVersion(self, obj):
        latest = TermsVersion.cached.cached_latest()
        return obj.agreed_terms_version == latest.version

    class Meta(DetailSerializerV2.Meta):
        model = BadgeUser
        apispec_definition = ('BadgeUser', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this BadgeUser",
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"BadgeUser\"",
                }),
                ('firstName', {
                    'type': "string",
                    'format': "string",
                    'description': "Given name",
                }),
                ('lastName', {
                    'type': "string",
                    'format': "string",
                    'description': "Family name",
                }),
            ]),
        })

    def update(self, instance, validated_data):
        password = validated_data.pop('password') if 'password' in validated_data else None
        current_password = validated_data.pop('currentPassword') if 'currentPassword' in validated_data else None
        super(BadgeUserSerializerV2, self).update(instance, validated_data)

        if password:
            if not current_password:
                raise serializers.ValidationError({'current_password': "Field is required"})
            if instance.check_password(current_password):
                instance.set_password(password)
                notify_on_password_change(instance)
            else:
                raise serializers.ValidationError({'current_password': "Incorrect password"})

        instance.badgrapp = BadgrApp.objects.get_current(request=self.context.get('request', None))

        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super(BadgeUserSerializerV2, self).to_representation(instance)

        latest = TermsVersion.cached.cached_latest()
        if latest:
            representation['latestTermsVersion'] = latest.version
            if latest.version != instance.agreed_terms_version:
                representation['latestTermsDescription'] = latest.short_description

        if not self.context.get('isSelf'):
            fields_shown_only_to_self = ['emails']
            for f in fields_shown_only_to_self:
                if f in representation['result'][0]:
                    del representation['result'][0][f]
        return representation


class BadgeUserTokenSerializerV2(BaseSerializerV2):
    token = serializers.CharField(read_only=True, source='cached_token')

    class Meta:
        list_serializer_class = ListSerializerV2
        apispec_definition = ('BadgeUserToken', {
            'properties': OrderedDict([
                ('token', {
                    'type': "string",
                    'format': "string",
                    'description': "Access token to use in the Authorization header",
                }),
            ])
        })

    def update(self, instance, validated_data):
        # noop
        return instance


class AccessTokenSerializerV2(DetailSerializerV2):
    application = ApplicationInfoSerializer(source='applicationinfo')
    scope = serializers.CharField(read_only=True)
    expires = DateTimeWithUtcZAtEndField(read_only=True)
    created = DateTimeWithUtcZAtEndField(read_only=True)

    class Meta:
        list_serializer_class = ListSerializerV2
        apispec_definition = ('AccessToken', {})


class TermsVersionSerializerV2(DetailSerializerV2):
    version = serializers.IntegerField(read_only=True)
    shortDescription = serializers.CharField(read_only=True, source='short_description')
    created = DateTimeWithUtcZAtEndField(read_only=True, source='created_at')
    updated = DateTimeWithUtcZAtEndField(read_only=True, source='updated_at')
