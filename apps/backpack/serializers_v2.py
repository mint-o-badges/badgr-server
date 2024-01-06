# encoding: utf-8


from collections import OrderedDict

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as RestframeworkValidationError

from backpack.models import BackpackCollection
from entity.serializers import DetailSerializerV2, EntityRelatedFieldV2
from issuer.helpers import BadgeCheckHelper
from issuer.models import BadgeInstance, BadgeClass, Issuer
from issuer.serializers_v2 import BadgeRecipientSerializerV2, EvidenceItemSerializerV2
from mainsite.drf_fields import ValidImageField
from mainsite.serializers import DateTimeWithUtcZAtEndField, MarkdownCharField
from mainsite.serializers import HumanReadableBooleanField, OriginalJsonSerializerMixin


class BackpackAssertionSerializerV2(DetailSerializerV2, OriginalJsonSerializerMixin):
    acceptance = serializers.ChoiceField(choices=BadgeInstance.ACCEPTANCE_CHOICES,
            default=BadgeInstance.ACCEPTANCE_ACCEPTED)

    # badgeinstance
    openBadgeId = serializers.URLField(source='jsonld_id', read_only=True)
    badgeclass = EntityRelatedFieldV2(source='cached_badgeclass', required=False, queryset=BadgeClass.cached)
    badgeclassOpenBadgeId = serializers.URLField(source='badgeclass_jsonld_id', read_only=True)
    issuer = EntityRelatedFieldV2(source='cached_issuer', required=False, queryset=Issuer.cached)
    issuerOpenBadgeId = serializers.URLField(source='issuer_jsonld_id', read_only=True)

    name = serializers.CharField(source='cached_badgeclass.name', read_only=True)
    image = serializers.FileField(read_only=True)
    recipient = BadgeRecipientSerializerV2(source='*')
    issuedOn = DateTimeWithUtcZAtEndField(source='issued_on', read_only=True)
    narrative = MarkdownCharField(required=False)
    evidence = EvidenceItemSerializerV2(many=True, required=False)
    revoked = HumanReadableBooleanField(read_only=True)
    revocationReason = serializers.CharField(source='revocation_reason', read_only=True)
    expires = DateTimeWithUtcZAtEndField(source='expires_at', required=False)
    pending = serializers.ReadOnlyField()

    class Meta(DetailSerializerV2.Meta):
        model = BadgeInstance
        apispec_definition = ('BackpackAssertion', {
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
                    'readOnly': True,
                }),
                ('image', {
                    'type': 'string',
                    'format': 'url',
                    'description': "URL to the baked assertion image",
                    'readOnly': True,
                }),
                ('recipient', {
                    'type': 'object',
                    'properties': OrderedDict([
                        ('identity', {
                            'type': 'string',
                            'format': 'string',
                            'description': 'Either the hash of the identity or the plaintext value',
                            'required': True,
                        }),
                        ('type', {
                            'type': 'string',
                            'enum': [c[0] for c in BadgeInstance.RECIPIENT_TYPE_CHOICES],
                            'description': "Type of identifier used to identify recipient",
                            'required': False,
                        }),
                        ('hashed', {
                            'type': 'boolean',
                            'description': "Whether or not the identity value is hashed.",
                            'required': False,
                        }),
                        ('plaintextIdentity', {
                            'type': 'string',
                            'description': "The plaintext identity",
                            'required': False,
                        }),
                    ]),
                    'description': "Recipient that was issued the Assertion",
                    'required': True,
                }),
                ('issuedOn', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion was issued",
                    'required': True,
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
                ('expires', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion expires",
                    'required': False,
                }),

            ])
        })

    def to_representation(self, instance):
        representation = super(BackpackAssertionSerializerV2, self).to_representation(instance)
        request_kwargs = self.context['kwargs']
        expands = request_kwargs.get('expands', [])

        if self.parent is not None:
            # we'll have a bare representation
            instance_data_pointer = representation
        else:
            instance_data_pointer = representation['result'][0]

        if 'badgeclass' in expands:
            instance_data_pointer['badgeclass'] = instance.cached_badgeclass.get_json(
                    include_extra=True, use_canonical_id=True)
            if 'issuer' in expands:
                instance_data_pointer['badgeclass']['issuer'] = instance.cached_issuer.get_json(
                        include_extra=True, use_canonical_id=True)

        return representation


class BackpackAssertionAcceptanceSerializerV2(serializers.Serializer):
    acceptance = serializers.ChoiceField(choices=[BadgeInstance.ACCEPTANCE_ACCEPTED], write_only=True)

    def update(self, instance, validated_data):
        instance.acceptance = 'Accepted'

        instance.save()
        owner = instance.user
        if owner:
            owner.publish()

        return instance


class BackpackCollectionSerializerV2(DetailSerializerV2):
    name = serializers.CharField()
    description = MarkdownCharField(required=False)
    owner = EntityRelatedFieldV2(read_only=True, source='created_by')
    share_url = serializers.URLField(read_only=True)
    shareHash = serializers.CharField(read_only=True, source='share_hash')
    published = serializers.BooleanField(required=False)

    assertions = EntityRelatedFieldV2(many=True, source='badge_items',
            required=False, queryset=BadgeInstance.cached)

    class Meta(DetailSerializerV2.Meta):
        model = BackpackCollection
        apispec_definition = ('Collection', {
            'properties': OrderedDict([
                ('entityId', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this Collection",
                }),
                ('entityType', {
                    'type': "string",
                    'format': "string",
                    'description': "\"Collection\"",
                }),
                ('createdAt', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Collection was created",
                }),
                ('createdBy', {
                    'type': 'string',
                    'format': 'entityId',
                    'description': "BadgeUser who created this Collection",
                }),

                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name of the Collection",
                }),
                ('description', {
                    'type': "string",
                    'format': "text",
                    'description': "Short description of the Collection",
                }),
                ('share_url', {
                    'type': "string",
                    'format': "url",
                    'description': "A public URL for sharing the Collection. Read only.",
                }),
                ('shareHash', {
                    'type': "string",
                    'format': "url",
                    'description': "The share hash that allows construction of "
                                   "a public sharing URL. Read only.",
                }),
                ('published', {
                    'type': "boolean",
                    'description': "True if the Collection has a public share URL",
                }),
                ('assertions', {
                    'type': "array",
                    'items': {
                        '$ref': '#/definitions/Assertion'
                    },
                    'description': "List of Assertions in the collection",
                }),
            ])
        })


class BackpackImportSerializerV2(DetailSerializerV2):
    url = serializers.URLField(required=False)
    image = ValidImageField(required=False)
    assertion = serializers.DictField(required=False)

    def validate(self, attrs):
        # TODO: when test is run, why is assertion field blank???
        if sum(1 if v else 0 for v in list(attrs.values())) != 1:
            raise serializers.ValidationError(
                    "Must provide only one of 'url', 'image' or 'assertion'.")
        return attrs

    def create(self, validated_data):
        try:
            validated_data['imagefile'] = validated_data.pop('image', None)
            instance, created = BadgeCheckHelper.get_or_create_assertion(**validated_data)
            if not created:
                if instance.acceptance == BadgeInstance.ACCEPTANCE_ACCEPTED:
                    raise RestframeworkValidationError(
                        [{'name': "DUPLICATE_BADGE",
                            'description': "You already have this badge in your backpack"}])
                instance.acceptance = BadgeInstance.ACCEPTANCE_ACCEPTED
                instance.save()
        except DjangoValidationError as e:
            raise RestframeworkValidationError(e.messages)
        return instance
