from collections import OrderedDict
import os
import pytz
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator, EmailValidator
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from badgeuser.models import BadgeUser
from badgeuser.serializers_v2 import BadgeUserEmailSerializerV2
from entity.serializers import DetailSerializerV2, EntityRelatedFieldV2, BaseSerializerV2
from issuer.models import Issuer, IssuerStaff, BadgeClass, SuperBadge, CollectionBadgeContainer, BadgeInstance, CollectionBadgeInstance, \
        RECIPIENT_TYPE_EMAIL, RECIPIENT_TYPE_ID, RECIPIENT_TYPE_URL, RECIPIENT_TYPE_TELEPHONE
from issuer.permissions import IsEditor
from issuer.utils import generate_sha256_hashstring, request_authenticated_with_server_admin_token
from mainsite.drf_fields import ValidImageField
from mainsite.models import BadgrApp
from mainsite.serializers import CachedUrlHyperlinkedRelatedField, \
        DateTimeWithUtcZAtEndField, StripTagsCharField, MarkdownCharField, \
        HumanReadableBooleanField, OriginalJsonSerializerMixin
from mainsite.validators import ChoicesValidator, TelephoneValidator, \
        BadgeExtensionValidator, PositiveIntegerValidator


class IssuerAccessTokenSerializerV2(BaseSerializerV2):
    token = serializers.CharField()
    issuer = serializers.CharField()
    expires = DateTimeWithUtcZAtEndField()

    class Meta(DetailSerializerV2.Meta):
        apispec_definition = ('AccessToken', {})

    def to_representation(self, instance):
        return super(IssuerAccessTokenSerializerV2, self).to_representation(instance)


class StaffUserProfileSerializerV2(DetailSerializerV2):
    firstName = StripTagsCharField(source='first_name', read_only=True)
    lastName = StripTagsCharField(source='last_name', read_only=True)
    emails = BadgeUserEmailSerializerV2(many=True, source='email_items', read_only=True)
    url = serializers.ListField(child=serializers.URLField(),
                                read_only=True,
                                source='cached_verified_urls',
                                max_length=100)
    telephone = serializers.ListField(child=serializers.CharField(),
                                      read_only=True,
                                      source='cached_verified_phone_numbers',
                                      max_length=100)
    badgrDomain = serializers.CharField(read_only=True, max_length=255, source='badgrapp')


class IssuerStaffSerializerV2(DetailSerializerV2):
    userProfile = StaffUserProfileSerializerV2(source='cached_user', read_only=True)
    user = EntityRelatedFieldV2(source='cached_user', queryset=BadgeUser.cached)
    role = serializers.CharField(validators=[ChoicesValidator(list(dict(IssuerStaff.ROLE_CHOICES).keys()))])

    class Meta(DetailSerializerV2.Meta):
        apispec_definition = ('IssuerStaff', {
            'properties': {
                'role': {
                    'type': "string",
                    'enum': ["staff", "editor", "owner"]

                }
            }
        })


class IssuerSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    openBadgeId = serializers.URLField(source='jsonld_id', read_only=True)
    createdAt = DateTimeWithUtcZAtEndField(source='created_at', read_only=True)
    createdBy = EntityRelatedFieldV2(source='cached_creator', queryset=BadgeUser.cached, required=False)
    name = StripTagsCharField(max_length=1024)
    image = ValidImageField(required=False, use_public=True, source='*')
    email = serializers.EmailField(max_length=255, required=True) 
    description = StripTagsCharField(max_length=16384, required=False)
    url = serializers.URLField(max_length=1024, required=True)
    staff = IssuerStaffSerializerV2(many=True, source='staff_items', required=False)
    extensions = serializers.DictField(source='extension_items', required=False, validators=[BadgeExtensionValidator()])
    badgrDomain = serializers.SlugRelatedField(
        required=False, source='badgrapp', slug_field='cors', queryset=BadgrApp.objects
    )

    class Meta(DetailSerializerV2.Meta):
        model = Issuer
        apispec_definition = ('Issuer', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this Issuer",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"Issuer\"",
                    'readOnly': True,
                }),
                ('openBadgeId', {
                    'type': "string",
                    'format': "url",
                    'description': "URL of the OpenBadge compliant json",
                    'readOnly': True,
                }),
                ('createdAt', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Issuer was created",
                    'readOnly': True,
                }),
                ('createdBy', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeUser who created this Issuer",
                    'required': False,
                }),

                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name of the Issuer",
                    'required': True,
                }),
                ('image', {
                    'type': "string",
                    'format': "data:image/png;base64",
                    'description': "Base64 encoded string of an image that represents the Issuer",
                    'required': False,
                }),
                ('email', {
                    'type': "string",
                    'format': "email",
                    'description': "Contact email for the Issuer",
                    'required': True,
                }),
                ('url', {
                    'type': "string",
                    'format': "url",
                    'description': "Homepage or website associated with the Issuer",
                    'required': False,
                }),
                ('description', {
                    'type': "string",
                    'format': "text",
                    'description': "Short description of the Issuer",
                    'required': False,
                }),

            ])
        })

    def validate_image(self, image):
        if image is not None:
            img_name, img_ext = os.path.splitext(image.name)
            image.name = 'issuer_logo_' + str(uuid.uuid4()) + img_ext
        return image

    def validate_createdBy(self, val):
        if not request_authenticated_with_server_admin_token(self.context.get('request')):
            return None
        return val

    def validate(self, data):
        if data.get('badgrapp') and not request_authenticated_with_server_admin_token(self.context.get('request')):
            data.pop('badgrapp')
        return data

    def create(self, validated_data):
        request = self.context.get('request')

        # If a Server Admin declares another user as creator, set it to that other user. Otherwise, use request.user
        user = validated_data.pop('cached_creator', None)
        if user:
            validated_data['created_by'] = user

        potential_email = validated_data['email']
        if validated_data.get('badgrapp') is None:
            validated_data['badgrapp'] = BadgrApp.objects.get_current(request)

        # Server admins are exempt from email verification requirement. They will enforce it themselves.
        if (not request_authenticated_with_server_admin_token(request)
                and not validated_data['created_by'].is_email_verified(potential_email)):
            raise serializers.ValidationError(
                "Issuer email must be one of your verified addresses. Add this email to your profile and try again.")

        staff = validated_data.pop('staff_items', [])
        new_issuer = super(IssuerSerializerV2, self).create(validated_data)

        # update staff after issuer is created
        new_issuer.staff_items = staff

        return new_issuer

    def update(self, instance, validated_data):
        validated_data.pop('cached_creator', None)

        if 'image' in validated_data:
            self.context['save_kwargs'] = dict(force_resize=True)

        return super(IssuerSerializerV2, self).update(instance, validated_data)

    def to_representation(self, instance):
        from backpack.api import _scrub_boolean

        include_staff = _scrub_boolean(self.context['request'].query_params.get('include_staff', True))
        if self.fields.get('staff') and not include_staff:
            self.fields.pop('staff')
        return super(IssuerSerializerV2, self).to_representation(instance)


class AlignmentItemSerializerV2(BaseSerializerV2, OriginalJsonSerializerMixin):
    targetName = StripTagsCharField(source='target_name')
    targetUrl = serializers.URLField(source='target_url')
    targetDescription = StripTagsCharField(source='target_description',
                                           required=False, allow_null=True, allow_blank=True)
    targetFramework = StripTagsCharField(source='target_framework', required=False, allow_null=True, allow_blank=True)
    targetCode = StripTagsCharField(source='target_code', required=False, allow_null=True, allow_blank=True)

    class Meta:
        apispec_definition = ('BadgeClassAlignment', {
            'properties': {
            }
        })


class BadgeClassExpirationSerializerV2(serializers.Serializer):
    amount = serializers.IntegerField(source='expires_amount', allow_null=True, validators=[PositiveIntegerValidator()])
    duration = serializers.ChoiceField(source='expires_duration', allow_null=True,
                                       choices=BadgeClass.EXPIRES_DURATION_CHOICES)

    class Meta:
        apispec_definition = ('BadgeClassExpiration', {
            'properties': {
            }
        })


class BadgeClassSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    openBadgeId = serializers.URLField(source='jsonld_id', read_only=True)
    createdAt = DateTimeWithUtcZAtEndField(source='created_at', read_only=True)
    createdBy = EntityRelatedFieldV2(source='cached_creator', read_only=True)
    issuer = EntityRelatedFieldV2(source='cached_issuer', required=False, queryset=Issuer.cached)
    issuerOpenBadgeId = serializers.URLField(source='issuer_jsonld_id', read_only=True)

    name = StripTagsCharField(max_length=1024)
    image = ValidImageField(required=False, use_public=True, source='*')
    description = StripTagsCharField(max_length=16384, required=True, convert_null=True)

    criteriaUrl = StripTagsCharField(source='criteria_url', required=False,
                                     allow_null=True, validators=[URLValidator()])
    criteriaNarrative = MarkdownCharField(source='criteria_text', required=False, allow_null=True)

    alignments = AlignmentItemSerializerV2(source='alignment_items', many=True, required=False)
    tags = serializers.ListField(child=StripTagsCharField(max_length=1024), source='tag_items', required=False)

    expires = BadgeClassExpirationSerializerV2(source='*', required=False, allow_null=True)

    extensions = serializers.DictField(source='extension_items', required=False, validators=[BadgeExtensionValidator()])

    class Meta(DetailSerializerV2.Meta):
        model = BadgeClass
        apispec_definition = ('BadgeClass', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this BadgeClass",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"BadgeClass\"",
                    'readOnly': True,
                }),
                ('openBadgeId', {
                    'type': "string",
                    'format': "url",
                    'description': "URL of the OpenBadge compliant json",
                    'readOnly': True,
                }),
                ('createdAt', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the BadgeClass was created",
                    'readOnly': True,
                }),
                ('createdBy', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeUser who created this BadgeClass",
                    'readOnly': True,
                }),

                ('issuer', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "entityId of the Issuer who owns the BadgeClass",
                    'required': False,
                }),

                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name of the BadgeClass",
                    'required': True,
                }),
                ('description', {
                    'type': "string",
                    'format': "string",
                    'description': "Short description of the BadgeClass",
                    'required': True,
                }),
                ('image', {
                    'type': "string",
                    'format': "data:image/png;base64",
                    'description': "Base64 encoded string of an image that represents the BadgeClass.",
                    'required': False,
                }),
                ('criteriaUrl', {
                    'type': "string",
                    'format': "url",
                    'description': ("External URL that describes in a human-readable "
                        "format the criteria for the BadgeClass"),
                    'required': False,
                }),
                ('criteriaNarrative', {
                    'type': "string",
                    'format': "markdown",
                    'description': "Markdown formatted description of the criteria",
                    'required': False,
                }),
                ('tags', {
                    'type': "array",
                    'items': {
                        'type': "string",
                        'format': "string"
                    },
                    'description': "List of tags that describe the BadgeClass",
                    'required': False,
                }),
                ('alignments', {
                    'type': "array",
                    'items': {
                        '$ref': '#/definitions/BadgeClassAlignment'
                    },
                    'description': "List of objects describing objectives or educational standards",
                    'required': False,
                }),
                ('expires', {
                    '$ref': "#/definitions/BadgeClassExpiration",
                    'description': "Expiration period for Assertions awarded from this BadgeClass",
                    'required': False,
                }),
            ])
        })

    def to_internal_value(self, data):
        if not isinstance(data, BadgeClass) and 'expires' in data:
            if not data['expires'] or len(data['expires']) == 0:
                # if expires was included blank, remove it so to_internal_value() doesnt choke
                del data['expires']
        return super(BadgeClassSerializerV2, self).to_internal_value(data)

    def update(self, instance, validated_data):
        if 'cached_issuer' in validated_data:
            validated_data.pop('cached_issuer')  # issuer is not updatable

        if 'image' in validated_data:
            self.context['save_kwargs'] = dict(force_resize=True)

        # Verify that criteria won't be empty
        if 'criteria_url' in validated_data or 'criteria_text' in validated_data:
            end_criteria_url = validated_data['criteria_url'] if 'criteria_url' in validated_data \
                else instance.criteria_url
            end_criteria_text = validated_data['criteria_text'] if 'criteria_text' in validated_data \
                else instance.criteria_text

            if ((end_criteria_url is None or not end_criteria_url.strip())
                    and (end_criteria_text is None or not end_criteria_text.strip())):
                raise serializers.ValidationError('Changes cannot be made that would leave both criteria_url and '
                                                  'criteria_text blank.')

        if not IsEditor().has_object_permission(self.context.get('request'), None, instance.issuer):
            raise serializers.ValidationError(
                {"issuer": "You do not have permission to edit badges on this issuer."})

        return super(BadgeClassSerializerV2, self).update(instance, validated_data)

    def create(self, validated_data):
        if 'image' not in validated_data:
            raise serializers.ValidationError({'image': 'Valid image file or data URI required.'})
        if 'cached_issuer' in validated_data:
            # included issuer in request
            validated_data['issuer'] = validated_data.pop('cached_issuer')
        elif 'issuer' in self.context:
            # issuer was passed in context
            validated_data['issuer'] = self.context.get('issuer')
        else:
            # issuer is required on create
            raise serializers.ValidationError({"issuer": "This field is required"})
        if 'criteria_url' not in validated_data and 'criteria_text' not in validated_data:
            raise serializers.ValidationError("A criteria_url or criteria_test is required.")

        if not IsEditor().has_object_permission(self.context.get('request'), None, validated_data['issuer']):
            raise serializers.ValidationError({"issuer": "You do not have permission to edit badges on this issuer."})

        return super(BadgeClassSerializerV2, self).create(validated_data)

class ModifiedRelatedField(serializers.RelatedField):
    def get_choices(self, cutoff=None):
        queryset = self.get_queryset()
        if queryset is None:
            return {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        return OrderedDict([
            (
                item.pk,
                self.display_value(item)
            )
            for item in queryset
        ])
        
class CollectionBadgeBadgeClassField(ModifiedRelatedField):
    def to_representation(self, value):
        return {
                "id": value.entity_id,
                "name": value.name,
                "description": value.description,
                "image": value.image.url
                }

    def to_internal_value(self, data):
        return BadgeClass.objects.get(entity_id=data)  

class CollectionBadgeClassSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    name = StripTagsCharField(max_length=1024)
    image = ValidImageField(required=False, source='*')
    description = StripTagsCharField(max_length=16384, required=True, convert_null=True)

    assertions = CollectionBadgeBadgeClassField(many=True, source='badgeclass_items',
            required=False, queryset=BadgeClass.cached)    


    class Meta(DetailSerializerV2.Meta):
        model = CollectionBadgeContainer
        apispec_definition = ('CollectionBadgeClass', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this CollectionBadgeClass",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"CollectionBadgeClass\"",
                    'readOnly': True,
                }),

                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name of the CollectionBadgeClass",
                    'required': True,
                }),
                ('description', {
                    'type': "string",
                    'format': "string",
                    'description': "Short description of the CollectionBadgeClass",
                    'required': True,
                }),
                ('image', {
                    'type': "string",
                    'format': "data:image/png;base64",
                    'description': "Base64 encoded string of an image that represents the CollectionBadgeClass.",
                    'required': False,
                }),
                ('assertions', {
                    'type': "array",
                    # 'items': {
                    #     '$ref': '#/definitions/Assertion'
                    # },
                    'description': "List of Assertions in the CollectionBadge",
                }),
            ])
        })

    def to_internal_value(self, data):
        return super(CollectionBadgeClassSerializerV2, self).to_internal_value(data)

    def create(self, validated_data):
        if 'image' not in validated_data:
            raise serializers.ValidationError({'image': 'Valid image file or data URI required.'})
       
        return super(CollectionBadgeClassSerializerV2, self).create(validated_data)

class SuperBadgeBadgeClassField(ModifiedRelatedField):
    def to_representation(self, value):
        return {
                "id": value.entity_id,
                "name": value.name,
                "description": value.description,
                "image": value.image.url
                }

    def to_internal_value(self, data):
        return BadgeClass.objects.get(entity_id=data) 

class SuperBadgeClassSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    name = StripTagsCharField(max_length=1024)
    image = ValidImageField(required=False, source='*')
    description = StripTagsCharField(max_length=16384, required=True, convert_null=True)

    assertions = SuperBadgeBadgeClassField(many=True, source='badge_items',
            required=False, queryset=BadgeClass.cached)

    class Meta(DetailSerializerV2.Meta):
        model = SuperBadge
        apispec_definition = ('SuperBadgeClass', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this SuperBadgeClass",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"SuperBadgeClass\"",
                    'readOnly': True,
                }),
                # ('createdAt', {
                #     'type': 'string',
                #     'format': 'ISO8601 timestamp',
                #     'description': "Timestamp when the BadgeClass was created",
                #     'readOnly': True,
                # }),
                # ('createdBy', {
                #     'type': 'string',
                #     'format': 'entityId',
                #     'description': "BadgeUser who created this BadgeClass",
                #     'readOnly': True,
                # }),

                # ('issuer', {
                #     'type': 'string',
                #     'format': 'entityId',
                #     'description': "entityId of the Issuer who owns the BadgeClass",
                #     'required': False,
                # }),

                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name of the SuperBadgeClass",
                    'required': True,
                }),
                ('description', {
                    'type': "string",
                    'format': "string",
                    'description': "Short description of the SuperBadgeClass",
                    'required': True,
                }),
                ('image', {
                    'type': "string",
                    'format': "data:image/png;base64",
                    'description': "Base64 encoded string of an image that represents the SuperBadgeClass.",
                    'required': False,
                }),
                ('assertions', {
                    'type': "array",
                    # 'items': {
                    #     '$ref': '#/definitions/Assertion'
                    # },
                    'description': "List of Assertions in the SuperBadge",
                }),
            ])
        })

    def to_internal_value(self, data):
        return super(SuperBadgeClassSerializerV2, self).to_internal_value(data)

    def create(self, validated_data):
        if 'image' not in validated_data:
            raise serializers.ValidationError({'image': 'Valid image file or data URI required.'})
       
        return super(SuperBadgeClassSerializerV2, self).create(validated_data)


class BadgeRecipientSerializerV2(BaseSerializerV2):
    identity = serializers.CharField(source='recipient_identifier')
    hashed = serializers.NullBooleanField(default=None, required=False)
    type = serializers.ChoiceField(
        choices=BadgeInstance.RECIPIENT_TYPE_CHOICES,
        default=RECIPIENT_TYPE_EMAIL,
        required=False,
        source='recipient_type'
    )
    plaintextIdentity = serializers.CharField(source='recipient_identifier', read_only=True, required=False)

    VALIDATORS = {
        RECIPIENT_TYPE_EMAIL: EmailValidator(),
        RECIPIENT_TYPE_URL: URLValidator(),
        RECIPIENT_TYPE_ID: URLValidator(),
        RECIPIENT_TYPE_TELEPHONE: TelephoneValidator(),
    }
    HASHED_DEFAULTS = {
        RECIPIENT_TYPE_EMAIL: True,
        RECIPIENT_TYPE_URL: False,
        RECIPIENT_TYPE_ID: False,
        RECIPIENT_TYPE_TELEPHONE: True,

    }

    class Meta:
        apispec_definition = ('BadgeRecipient', {
            'properties': OrderedDict([
                ('identity', {
                    'type': 'string',
                    'format': 'string',
                    'description': 'Either the hash of the identity or the plaintext value'
                }),
                ('type', {
                    'type': 'string',
                    'enum': [c[0] for c in BadgeInstance.RECIPIENT_TYPE_CHOICES],
                    'description': "Type of identifier used to identify recipient"
                }),
                ('hashed', {
                    'type': 'boolean',
                    'description': "Whether or not the identity value is hashed."
                }),
                ('plaintextIdentity', {
                    'type': 'string',
                    'description': "The plaintext identity"
                }),
            ]),
        })

    def validate(self, attrs):
        recipient_type = attrs.get('recipient_type')
        recipient_identifier = attrs.get('recipient_identifier')
        hashed = attrs.get('hashed')
        if recipient_type in self.VALIDATORS:
            try:
                self.VALIDATORS[recipient_type](recipient_identifier)
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.message)
        if hashed is None:
            attrs['hashed'] = self.HASHED_DEFAULTS.get(recipient_type, True)
        return attrs

    def to_representation(self, instance):
        representation = super(BadgeRecipientSerializerV2, self).to_representation(instance)
        if instance.hashed:
            representation['salt'] = instance.salt
            representation['identity'] = generate_sha256_hashstring(instance.recipient_identifier, instance.salt)

        return representation


class EvidenceItemSerializerV2(BaseSerializerV2, OriginalJsonSerializerMixin):
    url = serializers.URLField(source='evidence_url', max_length=1024, required=False)
    narrative = MarkdownCharField(required=False)

    class Meta:
        apispec_definition = ('AssertionEvidence', {
            'properties': OrderedDict([
                ('url', {
                    'type': "string",
                    'format': "url",
                    'description': "URL of a webpage presenting evidence of the achievement",
                }),
                ('narrative', {
                    'type': "string",
                    'format': "markdown",
                    'description': "Markdown narrative that describes the achievement",
                }),
            ])
        })

    def validate(self, attrs):
        if not (attrs.get('evidence_url', None) or attrs.get('narrative', None)):
            raise serializers.ValidationError("Either url or narrative is required")

        return attrs


class BadgeInstanceSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    openBadgeId = serializers.URLField(source='jsonld_id', read_only=True)
    createdAt = DateTimeWithUtcZAtEndField(source='created_at', read_only=True, default_timezone=pytz.utc)
    createdBy = EntityRelatedFieldV2(source='cached_creator', read_only=True)
    badgeclass = EntityRelatedFieldV2(source='cached_badgeclass', required=False, queryset=BadgeClass.cached)
    badgeclassOpenBadgeId = CachedUrlHyperlinkedRelatedField(
        source='badgeclass_jsonld_id', view_name='badgeclass_json', lookup_field='entity_id',
        queryset=BadgeClass.cached, required=False)
    badgeclassName = serializers.CharField(write_only=True, required=False)

    issuer = EntityRelatedFieldV2(source='cached_issuer', required=False, queryset=Issuer.cached)
    issuerOpenBadgeId = serializers.URLField(source='issuer_jsonld_id', read_only=True)

    image = ValidImageField(read_only=True, use_public=True, source='*')
    recipient = BadgeRecipientSerializerV2(source='*', required=False)

    issuedOn = DateTimeWithUtcZAtEndField(source='issued_on', required=False, default_timezone=pytz.utc)
    narrative = MarkdownCharField(required=False, allow_null=True)
    evidence = EvidenceItemSerializerV2(source='evidence_items', many=True, required=False)

    revoked = HumanReadableBooleanField(read_only=True)
    revocationReason = serializers.CharField(source='revocation_reason', read_only=True)
    acceptance = serializers.CharField(read_only=True)

    expires = DateTimeWithUtcZAtEndField(source='expires_at', required=False,
                                         allow_null=True, default_timezone=pytz.utc)

    notify = HumanReadableBooleanField(write_only=True, required=False, default=False)
    allowDuplicateAwards = serializers.BooleanField(write_only=True, required=False, default=True)

    extensions = serializers.DictField(source='extension_items', required=False, validators=[BadgeExtensionValidator()])

    class Meta(DetailSerializerV2.Meta):
        model = BadgeInstance
        apispec_definition = ('Assertion', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this Assertion",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"Assertion\"",
                    'readOnly': True,
                }),
                ('openBadgeId', {
                    'type': "string",
                    'format': "url",
                    'description': "URL of the OpenBadge compliant json",
                    'readOnly': True,
                }),
                ('createdAt', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion was created",
                    'readOnly': True,
                }),
                ('createdBy', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeUser who created the Assertion",
                    'readOnly': True,
                }),

                ('badgeclass', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeClass that issued this Assertion",
                    'required': False,
                }),
                ('badgeclassOpenBadgeId', {
                    'type': 'string',
                    'format': 'url',
                    'description': "URL of the BadgeClass to award",
                    'required': False,
                }),
                ('badgeclassName', {
                    'type': 'string',
                    'format': 'string',
                    'description': "Name of BadgeClass to create assertion against, case insensitive",
                    'required': False,
                }),
                ('revoked', {
                    'type': 'boolean',
                    'description': "True if this Assertion has been revoked",
                    'readOnly': True,
                }),
                ('revocationReason', {
                    'type': 'string',
                    'format': "string",
                    'description': "Short description of why the Assertion was revoked",
                    'readOnly': True,
                }),
                ('acceptance', {
                    'type': 'string',
                    'description': "Recipient interaction with Assertion. One of: Unaccepted, Accepted, or Rejected",
                    'readOnly': True,
                }),
                ('image', {
                    'type': 'string',
                    'format': 'url',
                    'description': "URL to the baked assertion image",
                    'readOnly': True,
                }),
                ('issuedOn', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion was issued",
                    'required': False,
                }),
                ('narrative', {
                    'type': 'string',
                    'format': 'markdown',
                    'description': "Markdown narrative of the achievement",
                    'required': False,
                }),
                ('evidence', {
                    'type': 'array',
                    'items': {
                        '$ref': '#/definitions/AssertionEvidence'
                    },
                    'description': "List of evidence associated with the achievement",
                    'required': False,
                }),
                ('recipient', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeRecipient',
                    'description': "Recipient that was issued the Assertion",
                    'required': False,
                }),
                ('expires', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion expires",
                    'required': False,
                }),
            ])
        })

    def validate_issuedOn(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Only issuedOn dates in the past are acceptable.")
        if value.year < 1583:
            raise serializers.ValidationError(
                "Only issuedOn dates after the introduction of the Gregorian calendar are allowed.")
        return value

    def update(self, instance, validated_data):
        updateable_fields = [
            'evidence_items',
            'expires_at',
            'extension_items',
            'hashed',
            'issued_on',
            'narrative',
            'recipient_identifier',
            'recipient_type'
        ]

        for field_name in updateable_fields:
            if field_name in validated_data:
                setattr(instance, field_name, validated_data.get(field_name))
        instance.rebake(save=True)

        return instance

    def create(self, validated_data):
        if 'cached_issuer' in validated_data:
            # ignore issuer in request
            validated_data.pop('cached_issuer')
        return super().create(validated_data)

    def validate(self, data):
        request = self.context.get('request', None)
        expected_issuer = self.context.get('kwargs', {}).get('issuer')
        badgeclass_identifiers = ['badgeclass_jsonld_id', 'badgeclassName', 'cached_badgeclass', 'badgeclass']
        badge_instance_properties = list(data.keys())

        if 'badgeclass' in self.context:
            badge_instance_properties.append('badgeclass')

        if sum([el in badgeclass_identifiers for el in badge_instance_properties]) > 1:
            raise serializers.ValidationError(
                'Multiple badge class identifiers. '
                'Exactly one of the following badge class identifiers are allowed: '
                'badgeclass, badgeclassName, or badgeclassOpenBadgeId')

        if request and request.method != 'PUT':
            # recipient and badgeclass are only required on create, ignored on update
            if 'recipient_identifier' not in data:
                raise serializers.ValidationError({'recipient': ["This field is required"]})

            if 'cached_badgeclass' in data:
                # included badgeclass in request
                data['badgeclass'] = data.pop('cached_badgeclass')
            elif 'badgeclass' in self.context:
                # badgeclass was passed in context
                data['badgeclass'] = self.context.get('badgeclass')
            elif 'badgeclass_jsonld_id' in data:
                data['badgeclass'] = data.pop('badgeclass_jsonld_id')
            elif 'badgeclassName' in data:
                name = data.pop('badgeclassName')
                matches = BadgeClass.objects.filter(name=name, issuer=expected_issuer)
                len_matches = len(matches)
                if len_matches == 1:
                    data['badgeclass'] = matches.first()
                elif len_matches == 0:
                    raise serializers.ValidationError("No matching BadgeClass found with name {}".format(name))
                else:
                    raise serializers.ValidationError(
                        "Could not award; {} BadgeClasses with name {}".format(len_matches, name))
            else:
                raise serializers.ValidationError({"badgeclass": ["This field is required"]})

            allow_duplicate_awards = data.pop('allowDuplicateAwards')
            if allow_duplicate_awards is False:
                previous_awards = BadgeInstance.objects.filter(
                    recipient_identifier=data['recipient_identifier'], badgeclass=data['badgeclass']
                ).filter(
                    revoked=False
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
                )
                if previous_awards.exists():
                    raise serializers.ValidationError(
                        "A previous award of this badge already exists for this recipient.")

        if expected_issuer and data['badgeclass'].issuer_id != expected_issuer.id:
            raise serializers.ValidationError({"badgeclass": ["Could not find matching badgeclass for this issuer."]})

        if 'badgeclass' in data:
            data['issuer'] = data['badgeclass'].issuer

        return data

class CollectionBadgeInstanceSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    createdAt = DateTimeWithUtcZAtEndField(source='created_at', read_only=True, default_timezone=pytz.utc)
    createdBy = EntityRelatedFieldV2(source='cached_creator', read_only=True)
    collectionbadgeclass = EntityRelatedFieldV2(source='cached_collectionbadgeclass', required=False, queryset=CollectionBadgeContainer.cached)
    collectionbadgeclassName = serializers.CharField(write_only=True, required=False)

    issuer = EntityRelatedFieldV2(source='cached_issuer', required=False, queryset=Issuer.cached)

    image = ValidImageField(read_only=True, use_public=True, source='*')
    recipient = BadgeRecipientSerializerV2(source='*', required=False)

    issuedOn = DateTimeWithUtcZAtEndField(source='issued_on', required=False, default_timezone=pytz.utc)

    revoked = HumanReadableBooleanField(read_only=True)
    revocationReason = serializers.CharField(source='revocation_reason', read_only=True)
    acceptance = serializers.CharField(read_only=True)

    expires = DateTimeWithUtcZAtEndField(source='expires_at', required=False,
                                         allow_null=True, default_timezone=pytz.utc)

    notify = HumanReadableBooleanField(write_only=True, required=False, default=False)
    allowDuplicateAwards = serializers.BooleanField(write_only=True, required=False, default=True)


    class Meta(DetailSerializerV2.Meta):
        model = CollectionBadgeInstance
        apispec_definition = ('Assertion', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this Assertion",
                    'readOnly': True,
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"Assertion\"",
                    'readOnly': True,
                }),
                ('createdAt', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion was created",
                    'readOnly': True,
                }),
                ('createdBy', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeUser who created the Assertion",
                    'readOnly': True,
                }),

                ('collectionbadgeclass', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "CollectionBadgeClass that issued this Assertion",
                    'required': False,
                }),
                ('collectionbadgeclassName', {
                    'type': 'string',
                    'format': 'string',
                    'description': "Name of CollectionBadgeClass to create assertion against, case insensitive",
                    'required': False,
                }),
                ('revoked', {
                    'type': 'boolean',
                    'description': "True if this Assertion has been revoked",
                    'readOnly': True,
                }),
                ('revocationReason', {
                    'type': 'string',
                    'format': "string",
                    'description': "Short description of why the Assertion was revoked",
                    'readOnly': True,
                }),
                ('acceptance', {
                    'type': 'string',
                    'description': "Recipient interaction with Assertion. One of: Unaccepted, Accepted, or Rejected",
                    'readOnly': True,
                }),
                ('image', {
                    'type': 'string',
                    'format': 'url',
                    'description': "URL to the baked assertion image",
                    'readOnly': True,
                }),
                ('issuedOn', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion was issued",
                    'required': False,
                }),
                ('recipient', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeRecipient',
                    'description': "Recipient that was issued the Assertion",
                    'required': False,
                }),
                ('expires', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion expires",
                    'required': False,
                }),
            ])
        })

    def validate_issuedOn(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Only issuedOn dates in the past are acceptable.")
        if value.year < 1583:
            raise serializers.ValidationError(
                "Only issuedOn dates after the introduction of the Gregorian calendar are allowed.")
        return value

    def update(self, instance, validated_data):
        updateable_fields = [
            'expires_at',
            'hashed',
            'issued_on',
            'recipient_identifier',
            'recipient_type'
        ]

        for field_name in updateable_fields:
            if field_name in validated_data:
                setattr(instance, field_name, validated_data.get(field_name))

        return instance

    def create(self, validated_data):
        if 'cached_issuer' in validated_data:
            # ignore issuer in request
            validated_data.pop('cached_issuer')
        return super().create(validated_data)

    def validate(self, data):
        request = self.context.get('request', None)
        expected_issuer = self.context.get('kwargs', {}).get('issuer')
        collectionbadgeclass_identifiers = ['collectionbadgeclassName', 'cached_collectionbadgeclass', 'collectionbadgeclass']
        collectionbadge_instance_properties = list(data.keys())

        if 'collectionbadgeclass' in self.context:
            collectionbadge_instance_properties.append('collectionbadgeclass')

        if sum([el in collectionbadgeclass_identifiers for el in collectionbadge_instance_properties]) > 1:
            raise serializers.ValidationError(
                'Multiple collectionbadge class identifiers. '
                'Exactly one of the following badge class identifiers are allowed: '
                'badgeclass, badgeclassName')

        if request and request.method != 'PUT':
            # recipient and collectionbadgeclass are only required on create, ignored on update
            if 'recipient_identifier' not in data:
                raise serializers.ValidationError({'recipient': ["This field is required"]})

            if 'cached_collectionbadgeclass' in data:
                # included collectionbadgeclass in request
                data['collectionbadgeclass'] = data.pop('cached_collectionbadgeclass')
            elif 'collectionbadgeclass' in self.context:
                # collectionbadgeclass was passed in context
                data['collectionbadgeclass'] = self.context.get('collectionbadgeclass')
            elif 'collectionbadgeclassName' in data:
                name = data.pop('collectionbadgeclassName')
                matches = CollectionBadgeContainer.objects.filter(name=name, issuer=expected_issuer)
                len_matches = len(matches)
                if len_matches == 1:
                    data['collectionbadgeclass'] = matches.first()
                elif len_matches == 0:
                    raise serializers.ValidationError("No matching CollectionBadgeClass found with name {}".format(name))
                else:
                    raise serializers.ValidationError(
                        "Could not award; {} CollectionBadgeClasses with name {}".format(len_matches, name))
            else:
                raise serializers.ValidationError({"collectionbadgeclass": ["This field is required"]})

            allow_duplicate_awards = data.pop('allowDuplicateAwards')
            if allow_duplicate_awards is False:
                previous_awards = CollectionBadgeInstance.objects.filter(
                    recipient_identifier=data['recipient_identifier'], collectionbadgeclass=data['collectionbadgeclass']
                ).filter(
                    revoked=False
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
                )
                if previous_awards.exists():
                    raise serializers.ValidationError(
                        "A previous award of this badge already exists for this recipient.")

        if expected_issuer and data['collectionbadgeclass'].issuer_id != expected_issuer.id:
            raise serializers.ValidationError({"collectionbadgeclass": ["Could not find matching collectionbadgeclass for this issuer."]})

        if 'collectionbadgeclass' in data:
            data['issuer'] = data['collectionbadgeclass'].issuer

        return data        
