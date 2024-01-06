# encoding: utf-8
from __future__ import unicode_literals

from collections import OrderedDict

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as RestframeworkValidationError

from badgeuser.models import BadgeUser
from issuer.helpers import BadgeCheckHelper
from issuer.models import BadgeInstance
from issuer.serializers_v2 import BadgeRecipientSerializerV2, EvidenceItemSerializerV2
from mainsite.serializers import MarkdownCharField, HumanReadableBooleanField


CONTEXT_URI = 'https://w3id.org/openbadges/v2'


class BadgeConnectApiInfoSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    image = serializers.URLField(read_only=True)
    apiBase = serializers.URLField(read_only=True)
    version = serializers.CharField(read_only=True)
    termsOfServiceUrl = serializers.URLField(read_only=True)
    privacyPolicyUrl = serializers.URLField(read_only=True)
    scopesOffered = serializers.ListField(read_only=True, child=serializers.URLField())
    scopesRequested = serializers.ListField(read_only=True, child=serializers.URLField())
    registrationUrl = serializers.URLField(read_only=True)
    authorizationUrl = serializers.URLField(read_only=True)
    tokenUrl = serializers.URLField(read_only=True)

    class Meta:
        apispec_definition = ('BadgeConnectApiInfo', {
            'properties': OrderedDict([])
        })


class BadgeConnectManifestSerializer(serializers.Serializer):
    id = serializers.URLField(read_only=True)
    badgeConnectAPI = BadgeConnectApiInfoSerializer(read_only=True, many=True)

    class Meta:
        apispec_definition = ('BadgeConnectManifest', {
            'properties': OrderedDict([
                ('badgeConnectAPI', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeConnectApiInfo'
                }),
            ])
        })

    def to_representation(self, instance):
        data = super(BadgeConnectManifestSerializer, self).to_representation(instance)
        data['@context'] = 'https://w3id.org/openbadges/badgeconnect/v1'
        return data


class BadgeConnectStatusSerializer(serializers.Serializer):
    error = serializers.CharField(default=None)
    statusCode = serializers.IntegerField(default=200)
    statusText = serializers.CharField(default='OK')

    class Meta:
        apispec_definition = ('BadgeConnectStatus', {
            'properties': OrderedDict([
                ('error', {
                    'type': "string",
                    'readOnly': True,
                    'example': None,
                    'description': "Error text, if any",
                }),
                ('statusCode', {
                    'type': "integer",
                    'example': 200,
                    'readOnly': True,
                    'description': "Status code of request",
                }),
                ('statusText', {
                    'type': "string",
                    'readOnly': True,
                    'example': 'OK',
                    'description': "Status text of request",
                }),
            ])
        })


class BadgeConnectErrorSerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        self.error = kwargs.pop('error', None)
        self.status_text = kwargs.pop('status_text', 'BAD_REQUEST')
        self.status_code = kwargs.pop('status_code', 400)
        super(BadgeConnectErrorSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        return {
            "status": {
                "error": self.error,
                "statusCode": self.status_code,
                "statusText": self.status_text
            }
        }


class BadgeConnectBaseEntitySerializer(serializers.Serializer):
    def to_representation(self, instance):
        representation = super(BadgeConnectBaseEntitySerializer, self).to_representation(instance)
        representation['@context'] = CONTEXT_URI
        return representation


class BadgeConnectAssertionSerializer(BadgeConnectBaseEntitySerializer):
    id = serializers.URLField(source='jsonld_id', read_only=True)
    badge = serializers.URLField(source='badgeclass_jsonld_id', read_only=True)
    image = serializers.FileField(read_only=True)
    recipient = BadgeRecipientSerializerV2(source='*')
    issuedOn = serializers.DateTimeField(source='issued_on', read_only=True)
    narrative = MarkdownCharField(required=False)
    evidence = EvidenceItemSerializerV2(many=True, required=False)
    revoked = HumanReadableBooleanField(read_only=True)
    revocationReason = serializers.CharField(source='revocation_reason', read_only=True)
    expires = serializers.DateTimeField(source='expires_at', required=False)
    type = serializers.CharField(read_only=True, default='Assertion')

    class Meta:
        SCHEMA_TYPE = 'Assertion'
        model = BadgeInstance
        apispec_definition = ('BadgeConnectAssertion', {
            'properties': OrderedDict([
                ('id', {
                    'type': "string",
                    'format': "url",
                    'readOnly': True,
                    'description': "URL of the BadgeInstance",
                }),
                ('badge', {
                    'type': "string",
                    'format': "url",
                    'readOnly': True,
                    'description': "URL of the BadgeClass",
                }),
                ('image', {
                    'type': "string",
                    'format': "string",
                    'readOnly': True,
                    'description': "Badge Image",
                }),
                ('recipient', {
                    'type': 'object',
                    'properties': BadgeRecipientSerializerV2.Meta.apispec_definition[1]['properties'],
                    'readOnly': True,
                    'description': "Recipient that was issued the Assertion"
                }),
                ('issuedOn', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'readOnly': True,
                    'description': "Timestamp when the Assertion was issued",
                }),
                ('narrative', {
                    'type': 'string',
                    'format': 'markdown',
                    'description': "Markdown narrative of the achievement",
                }),
                ('evidence', {
                    'type': "string",
                    'format': "string",
                    'description': "Unique identifier for this Assertion",
                }),
                ('revoked', {
                    'type': 'boolean',
                    'readOnly': True,
                    'description': "True if this Assertion has been revoked",
                }),
                ('revocationReason', {
                    'type': 'string',
                    'format': "string",
                    'readOnly': True,
                    'description': "Short description of why the Assertion was revoked",
                }),
                ('expires', {
                    'type': 'string',
                    'format': 'ISO8601 timestamp',
                    'description': "Timestamp when the Assertion expires",
                }),
                ('@context', {
                    'type': 'string',
                    'format': 'url',
                    'default': CONTEXT_URI,
                    'example': CONTEXT_URI,
                }),
                ('type', {
                    'type': 'string',
                    'default': SCHEMA_TYPE,
                    'example': SCHEMA_TYPE
                })
            ])
        })


class BadgeConnectAssertionsSerializer(serializers.Serializer):
    status = BadgeConnectStatusSerializer(read_only=True, default={})
    results = BadgeConnectAssertionSerializer(many=True, source='*')

    class Meta:
        apispec_definition = ('BadgeConnectAssertions', {
            'properties': OrderedDict([
                ('status', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeConnectStatus'
                    }),
                ('results', {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        '$ref': '#/definitions/BadgeConnectAssertion'
                        }
                    })
                ])
            })


class BackpackImportResultSerializerBC(serializers.Serializer):
    status = BadgeConnectStatusSerializer(read_only=True, default={})

    class Meta:
        apispec_definition = ('BadgeConnectImportResult', {
            'properties': OrderedDict([
                ('status', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeConnectStatus'
                }),
            ])
        })


class BadgeConnectImportSerializer(serializers.Serializer):
    assertion = serializers.DictField()

    class Meta:
        apispec_definition = ('BadgeConnectImport', {
            'properties': OrderedDict([
                ('assertion', {
                    'type': 'object',
                    'properties': {
                        'id': {
                            'format': "url",
                            'description': "URL of the Badge to import"
                            }
                        }})
                    ])
            })

    def create(self, validated_data):
        url = validated_data['assertion']['id']
        try:
            instance, created = BadgeCheckHelper.get_or_create_assertion(url=url,
                    created_by=self.context['request'].user)
            if not created:
                instance.acceptance = BadgeInstance.ACCEPTANCE_ACCEPTED
                instance.save()
                raise RestframeworkValidationError([{'name': "DUPLICATE_BADGE",
                    'description': "You already have this badge in your backpack"}])
        except DjangoValidationError as e:
            raise RestframeworkValidationError(e.messages)
        return instance

    def to_representation(self, instance):
        serializer = BackpackImportResultSerializerBC({})
        return serializer.data


class BaseSerializerBC(serializers.Serializer):

    @staticmethod
    def response_envelope(result=None):
        envelope = {
            "status": {
                "error": None,
                "statusCode": 200,
                "statusText": 'OK',
            },
        }
        if result is not None:
            envelope['results'] = result

        return envelope


class BadgeConnectProfile(BadgeConnectBaseEntitySerializer):
    name = serializers.SerializerMethodField()
    email = serializers.EmailField()

    class Meta:
        model = BadgeUser
        apispec_definition = ('BadgeConnectProfile', {
            'properties': OrderedDict([
                ('name', {
                    'type': "string",
                    'format': "string",
                    'description': "Name on the profile",
                }),
                ('email', {
                    'type': "string",
                    'format': "email",
                    'description': "Email on the profile",
                }),
                ('@context', {
                    'type': 'string',
                    'format': 'url',
                    'default': CONTEXT_URI,
                    'example': CONTEXT_URI,
                })
            ])
        })

    def get_name(self, instance):
        return '%s %s' % (instance.first_name, instance.last_name)


class BackpackProfilesSerializerBC(serializers.Serializer):
    # This class is pluralized to be consistent with the shape of the data
    # it returns, however it should always contain 1 profile.
    status = BadgeConnectStatusSerializer(read_only=True, default={})
    results = BadgeConnectProfile(many=True, source='*')

    class Meta:
        model = BadgeUser
        apispec_definition = ('BadgeConnectProfiles', {
            'properties': OrderedDict([
                ('status', {
                    'type': 'object',
                    '$ref': '#/definitions/BadgeConnectStatus'
                }),
                ('results', {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        '$ref': '#/definitions/BadgeConnectProfile'
                        }
                    })
                ])
            })
