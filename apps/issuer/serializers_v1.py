import os
import pytz
import uuid
import json

import logging


from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.core.validators import EmailValidator, URLValidator
from django.db.models import Q
from django.utils.html import strip_tags
from django.utils import timezone
from rest_framework import serializers
from django.db import transaction
from json import loads as json_loads


from . import utils
from badgeuser.serializers_v1 import BadgeUserProfileSerializerV1, BadgeUserIdentifierFieldV1
from mainsite.drf_fields import ValidImageField
from mainsite.models import BadgrApp
from mainsite.serializers import DateTimeWithUtcZAtEndField, HumanReadableBooleanField, \
        StripTagsCharField, MarkdownCharField, OriginalJsonSerializerMixin
from mainsite.utils import OriginSetting, validate_altcha, verifyIssuerAutomatically
from mainsite.validators import ChoicesValidator, BadgeExtensionValidator, PositiveIntegerValidator, TelephoneValidator
from .models import Issuer, BadgeClass, IssuerStaff, BadgeInstance, BadgeClassExtension, \
        RECIPIENT_TYPE_EMAIL, RECIPIENT_TYPE_ID, RECIPIENT_TYPE_URL, LearningPath, LearningPathBadge, LearningPathParticipant, QrCode, RequestedBadge, RequestedLearningPath

from badgeuser.models import TermsVersion

logger = logging.getLogger(__name__)


class ExtensionsSaverMixin(object):
    def remove_extensions(self, instance, extensions_to_remove):
        extensions = instance.cached_extensions()
        for ext in extensions:
            if ext.name in extensions_to_remove:
                ext.delete()

    def update_extensions(self, instance, extensions_to_update, received_extension_items):
        logger.debug("UPDATING EXTENSION")
        logger.debug(received_extension_items)
        current_extensions = instance.cached_extensions()
        for ext in current_extensions:
            if ext.name in extensions_to_update:
                new_values = received_extension_items[ext.name]
                ext.original_json = json.dumps(new_values)
                ext.save()

    def save_extensions(self, validated_data, instance):
        logger.debug("SAVING EXTENSION IN MIXIN")
        logger.debug(validated_data.get('extension_items', False))
        if validated_data.get('extension_items', False):
            extension_items = validated_data.pop('extension_items')
            received_extensions = list(extension_items.keys())
            current_extension_names = list(instance.extension_items.keys())
            remove_these_extensions = set(current_extension_names) - set(received_extensions)
            update_these_extensions = set(current_extension_names).intersection(set(received_extensions))
            add_these_extensions = set(received_extensions) - set(current_extension_names)
            logger.debug(add_these_extensions)
            self.remove_extensions(instance, remove_these_extensions)
            self.update_extensions(instance, update_these_extensions, extension_items)
            self.add_extensions(instance, add_these_extensions, extension_items)


class CachedListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        return [self.child.to_representation(item) for item in data]


class IssuerStaffSerializerV1(serializers.Serializer):
    """ A read_only serializer for staff roles """
    user = BadgeUserProfileSerializerV1(source='cached_user')
    role = serializers.CharField(validators=[ChoicesValidator(list(dict(IssuerStaff.ROLE_CHOICES).keys()))])

    class Meta:
        list_serializer_class = CachedListSerializer

        apispec_definition = ('IssuerStaff', {
            'properties': {
                'role': {
                    'type': "string",
                    'enum': ["staff", "editor", "owner"]

                }
            }
        })


class IssuerSerializerV1(OriginalJsonSerializerMixin, serializers.Serializer):
    created_at = DateTimeWithUtcZAtEndField(read_only=True)
    created_by = BadgeUserIdentifierFieldV1()
    name = StripTagsCharField(max_length=1024)
    slug = StripTagsCharField(max_length=255, source='entity_id', read_only=True)
    image = ValidImageField(required=False)
    email = serializers.EmailField(max_length=255, required=True)
    description = StripTagsCharField(max_length=16384, required=False)
    url = serializers.URLField(max_length=1024, required=True)
    staff = IssuerStaffSerializerV1(read_only=True, source='cached_issuerstaff', many=True)
    badgrapp = serializers.CharField(read_only=True, max_length=255, source='cached_badgrapp')
    verified = serializers.BooleanField(default=False)

    category = serializers.CharField(max_length=255, required=True, allow_null=True)
    source_url = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    street = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    streetnumber = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    zip = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    intendedUseVerified = serializers.BooleanField(default=False)

    lat = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    lon = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    class Meta:
        apispec_definition = ('Issuer', {})

    def validate_image(self, image):
        if image is not None:
            img_name, img_ext = os.path.splitext(image.name)
            image.name = 'issuer_logo_' + str(uuid.uuid4()) + img_ext
        return image

    def create(self, validated_data, **kwargs):
        user = validated_data['created_by']
        potential_email = validated_data['email']


        if not user.is_email_verified(potential_email):
            raise serializers.ValidationError(
                "Issuer email must be one of your verified addresses. "
                "Add this email to your profile and try again.")
              
        new_issuer = Issuer(**validated_data)

        new_issuer.category = validated_data.get('category')
        new_issuer.street = validated_data.get('street')
        new_issuer.streetnumber = validated_data.get('streetnumber')
        new_issuer.zip = validated_data.get('zip')
        new_issuer.city = validated_data.get('city')
        new_issuer.country = validated_data.get('country')
        new_issuer.intendedUseVerified = validated_data.get('intendedUseVerified')

        # Check whether issuer email domain matches institution website domain to verify it automatically 
        if verifyIssuerAutomatically(validated_data.get('url'), validated_data.get('email')):
            new_issuer.verified = True
            
        # set badgrapp
        new_issuer.badgrapp = BadgrApp.objects.get_current(self.context.get('request', None))

        new_issuer.save()
        return new_issuer



    def update(self, instance, validated_data):
        force_image_resize = False
        instance.name = validated_data.get('name')

        if 'image' in validated_data:
            instance.image = validated_data.get('image')
            force_image_resize = True

        instance.email = validated_data.get('email')
        instance.description = validated_data.get('description')
        instance.url = validated_data.get('url')

        instance.category = validated_data.get('category')
        instance.street = validated_data.get('street')
        instance.streetnumber = validated_data.get('streetnumber')
        instance.zip = validated_data.get('zip')
        instance.city = validated_data.get('city')
        instance.country = validated_data.get('country')

        instance.intendedUseVerified = validated_data.get('intendedUseVerified')

        # set badgrapp
        if not instance.badgrapp_id:
            instance.badgrapp = BadgrApp.objects.get_current(self.context.get('request', None))

        instance.save(force_resize=force_image_resize)
        return instance

    def to_representation(self, obj):
        representation = super(IssuerSerializerV1, self).to_representation(obj)
        representation['json'] = obj.get_json(obi_version='1_1', use_canonical_id=True)

        if self.context.get('embed_badgeclasses', False):
            representation['badgeclasses'] = BadgeClassSerializerV1(
                obj.badgeclasses.all(), many=True, context=self.context).data
        representation['badgeClassCount'] = len(obj.cached_badgeclasses())
        representation['learningPathCount'] = len(obj.cached_learningpaths())
        representation['recipientGroupCount'] = 0
        representation['recipientCount'] = 0
        representation['pathwayCount'] = 0

        return representation


class IssuerRoleActionSerializerV1(serializers.Serializer):
    """ A serializer used for validating user role change POSTS """
    action = serializers.ChoiceField(('add', 'modify', 'remove'), allow_blank=True)
    username = serializers.CharField(allow_blank=True, required=False)
    email = serializers.EmailField(allow_blank=True, required=False)
    role = serializers.CharField(
        validators=[ChoicesValidator(list(dict(IssuerStaff.ROLE_CHOICES).keys()))],
        default=IssuerStaff.ROLE_STAFF)
    url = serializers.URLField(max_length=1024, required=False)
    telephone = serializers.CharField(max_length=100, required=False)

    def validate(self, attrs):
        identifiers = [attrs.get('username'), attrs.get('email'), attrs.get('url'), attrs.get('telephone')]
        identifier_count = len(list(filter(None.__ne__, identifiers)))
        if identifier_count > 1:
            raise serializers.ValidationError(
                'Please provided only one of the following: a username, email address, '
                'url, or telephone recipient identifier.'
            )
        return attrs


class AlignmentItemSerializerV1(serializers.Serializer):
    target_name = StripTagsCharField()
    target_url = serializers.URLField()
    target_description = StripTagsCharField(required=False, allow_blank=True, allow_null=True)
    target_framework = StripTagsCharField(required=False, allow_blank=True, allow_null=True)
    target_code = StripTagsCharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        apispec_definition = ('BadgeClassAlignment', {})


class BadgeClassExpirationSerializerV1(serializers.Serializer):
    amount = serializers.IntegerField(source='expires_amount', allow_null=True, validators=[PositiveIntegerValidator()])
    duration = serializers.ChoiceField(source='expires_duration', allow_null=True,
                                       choices=BadgeClass.EXPIRES_DURATION_CHOICES)


class BadgeClassSerializerV1(OriginalJsonSerializerMixin, ExtensionsSaverMixin, serializers.Serializer):
    created_at = DateTimeWithUtcZAtEndField(read_only=True)
    updated_at = DateTimeWithUtcZAtEndField(read_only=True)
    created_by = BadgeUserIdentifierFieldV1()
    id = serializers.IntegerField(required=False, read_only=True)
    name = StripTagsCharField(max_length=255)
    image = ValidImageField(required=False)
    imageFrame = serializers.BooleanField(default=True, required=False)
    slug = StripTagsCharField(max_length=255, read_only=True, source='entity_id')
    criteria = MarkdownCharField(allow_blank=True, required=False, write_only=True)
    criteria_text = MarkdownCharField(required=False, allow_null=True, allow_blank=True)
    criteria_url = StripTagsCharField(required=False, allow_blank=True, allow_null=True, validators=[URLValidator()])
    recipient_count = serializers.IntegerField(required=False, read_only=True, source='v1_api_recipient_count')
    description = StripTagsCharField(max_length=16384, required=True, convert_null=True)

    alignment = AlignmentItemSerializerV1(many=True, source='alignment_items', required=False)
    tags = serializers.ListField(child=StripTagsCharField(max_length=1024), source='tag_items', required=False)

    extensions = serializers.DictField(source='extension_items', required=False, validators=[BadgeExtensionValidator()])

    expires = BadgeClassExpirationSerializerV1(source='*', required=False, allow_null=True)

    source_url = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    issuerVerified = serializers.BooleanField(read_only=True, source='cached_issuer.verified')

    class Meta:
        apispec_definition = ('BadgeClass', {})

    def to_internal_value(self, data):
        if 'expires' in data:
            if not data['expires'] or len(data['expires']) == 0:
                # if expires was included blank, remove it so to_internal_value() doesnt choke
                del data['expires']
        return super(BadgeClassSerializerV1, self).to_internal_value(data)

    def to_representation(self, instance):
        exclude_orgImg = self.context.get('exclude_orgImg', None)
        representation = super(BadgeClassSerializerV1, self).to_representation(instance)
        representation['issuerName'] = instance.cached_issuer.name
        representation['issuerOwnerAcceptedTos'] = any(
            user.agreed_terms_version == TermsVersion.cached.latest_version() 
            for user in instance.cached_issuer.owners
        )
        representation['issuerVerifiedIntendedUse'] = instance.cached_issuer.intendedUseVerified
        representation['issuer'] = OriginSetting.HTTP + \
            reverse('issuer_json', kwargs={'entity_id': instance.cached_issuer.entity_id})
        representation['json'] = instance.get_json(obi_version='1_1', use_canonical_id=True)
        if 'extensions' in representation and exclude_orgImg:
            representation['extensions'] = {
                name: value 
                for name, value in representation['extensions'].items()
                if name != 'extensions:OrgImageExtension'
            }
        return representation

    def validate_image(self, image):
        if image is not None:
            img_name, img_ext = os.path.splitext(image.name)
            image.name = 'issuer_badgeclass_' + str(uuid.uuid4()) + img_ext
        return image

    def validate_criteria_text(self, criteria_text):
        if criteria_text is not None and criteria_text != '':
            return criteria_text
        else:
            return None

    def validate_criteria_url(self, criteria_url):
        if criteria_url is not None and criteria_url != '':
            return criteria_url
        else:
            return None

    def validate_extensions(self, extensions):
        is_formal = False
        if extensions:
            for ext_name, ext in extensions.items():
                # if "@context" in ext and not ext['@context'].startswith(settings.EXTENSIONS_ROOT_URL):
                #     raise BadgrValidationError(
                #         error_code=999,
                #         error_message=f"extensions @context invalid {ext['@context']}")
                if (ext_name.endswith('ECTSExtension')
                or ext_name.endswith('StudyLoadExtension')
                or ext_name.endswith('CategoryExtension')
                or ext_name.endswith('LevelExtension')
                or ext_name.endswith('CompetencyExtension')
                or ext_name.endswith('LicenseExtension')
                or ext_name.endswith('BasedOnExtension')):
                    is_formal = True
        self.formal = is_formal
        return extensions

    def add_extensions(self, instance, add_these_extensions, extension_items):
        for extension_name in add_these_extensions:
            original_json = extension_items[extension_name]
            extension = BadgeClassExtension(name=extension_name,
                                            original_json=json.dumps(original_json),
                                            badgeclass_id=instance.pk)
            extension.save()

    def update(self, instance, validated_data):
        logger.info("UPDATE BADGECLASS")
        logger.debug(validated_data)

        force_image_resize = False

        new_name = validated_data.get('name')
        if new_name:
            new_name = strip_tags(new_name)
            instance.name = new_name

        new_description = validated_data.get('description')
        if new_description:
            instance.description = strip_tags(new_description)

        # Assure both criteria_url and criteria_text will not be empty
        if 'criteria_url' in validated_data or 'criteria_text' in validated_data:
            end_criteria_url = validated_data['criteria_url'] if 'criteria_url' in validated_data \
                else instance.criteria_url
            end_criteria_text = validated_data['criteria_text'] if 'criteria_text' in validated_data \
                else instance.criteria_text

            if ((end_criteria_url is None or not end_criteria_url.strip())
                    and (end_criteria_text is None or not end_criteria_text.strip())):
                raise serializers.ValidationError(
                    'Changes cannot be made that would leave both criteria_url and criteria_text blank.'
                )
            else:
                instance.criteria_text = end_criteria_text
                instance.criteria_url = end_criteria_url

        if 'image' in validated_data:
            instance.image = validated_data.get('image')
            force_image_resize = True

        instance.alignment_items = validated_data.get('alignment_items')
        instance.tag_items = validated_data.get('tag_items')

        instance.expires_amount = validated_data.get('expires_amount', None)
        instance.expires_duration = validated_data.get('expires_duration', None)

        instance.imageFrame = validated_data.get('imageFrame', True)

        logger.debug("SAVING EXTENSION")
        self.save_extensions(validated_data, instance)

        instance.save(force_resize=force_image_resize)

        return instance

    def validate(self, data):
        if 'criteria' in data:
            if 'criteria_url' in data or 'criteria_text' in data:
                raise serializers.ValidationError(
                    "The criteria field is mutually-exclusive with the criteria_url and criteria_text fields"
                )

            if utils.is_probable_url(data.get('criteria')):
                data['criteria_url'] = data.pop('criteria')
            elif not isinstance(data.get('criteria'), str):
                raise serializers.ValidationError(
                    "Provided criteria text could not be properly processed as URL or plain text."
                )
            else:
                data['criteria_text'] = data.pop('criteria')
        return data

    def create(self, validated_data, **kwargs):

        logger.info("CREATE NEW BADGECLASS")
        logger.debug(validated_data)

        if 'image' not in validated_data:
            raise serializers.ValidationError({"image": ["This field is required"]})

        if 'issuer' in self.context:
            validated_data['issuer'] = self.context.get('issuer')

        if validated_data.get('criteria_text', None) is None and validated_data.get('criteria_url', None) is None:
            raise serializers.ValidationError(
                "One or both of the criteria_text and criteria_url fields must be provided"
            )

        new_badgeclass = BadgeClass.objects.create(**validated_data)
        return new_badgeclass


class EvidenceItemSerializer(serializers.Serializer):
    evidence_url = serializers.URLField(max_length=1024, required=False, allow_blank=True)
    narrative = MarkdownCharField(required=False, allow_blank=True)

    class Meta:
        apispec_definition = ('AssertionEvidence', {})

    def validate(self, attrs):
        if not (attrs.get('evidence_url', None) or attrs.get('narrative', None)):
            raise serializers.ValidationError("Either url or narrative is required")
        return attrs


class BadgeInstanceSerializerV1(OriginalJsonSerializerMixin, serializers.Serializer):
    created_at = DateTimeWithUtcZAtEndField(read_only=True, default_timezone=pytz.utc)
    created_by = BadgeUserIdentifierFieldV1(read_only=True)
    slug = serializers.CharField(max_length=255, read_only=True, source='entity_id')
    image = serializers.FileField(read_only=True)  # use_url=True, might be necessary
    email = serializers.EmailField(max_length=1024, required=False, write_only=True)
    recipient_identifier = serializers.CharField(max_length=1024, required=False)
    recipient_type = serializers.CharField(default=RECIPIENT_TYPE_EMAIL)
    allow_uppercase = serializers.BooleanField(default=False, required=False, write_only=True)
    evidence = serializers.URLField(write_only=True, required=False, allow_blank=True, max_length=1024)
    narrative = MarkdownCharField(required=False, allow_blank=True, allow_null=True)
    evidence_items = EvidenceItemSerializer(many=True, required=False)

    revoked = HumanReadableBooleanField(read_only=True)
    revocation_reason = serializers.CharField(read_only=True)

    expires = DateTimeWithUtcZAtEndField(source='expires_at', required=False,
                                         allow_null=True, default_timezone=pytz.utc)

    create_notification = HumanReadableBooleanField(write_only=True, required=False, default=False)
    allow_duplicate_awards = serializers.BooleanField(write_only=True, required=False, default=True)
    hashed = serializers.NullBooleanField(default=None, required=False)

    extensions = serializers.DictField(source='extension_items', required=False, validators=[BadgeExtensionValidator()])

    class Meta:
        apispec_definition = ('Assertion', {})

    def validate(self, data):
        recipient_type = data.get('recipient_type')
        if data.get('recipient_identifier') and data.get('email') is None:
            if recipient_type == RECIPIENT_TYPE_EMAIL:
                recipient_validator = EmailValidator()
            elif recipient_type in (RECIPIENT_TYPE_URL, RECIPIENT_TYPE_ID):
                recipient_validator = URLValidator()
            else:
                recipient_validator = TelephoneValidator()

            try:
                recipient_validator(data['recipient_identifier'])
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.message)

        elif data.get('email') and data.get('recipient_identifier') is None:
            data['recipient_identifier'] = data.get('email')

        allow_duplicate_awards = data.pop('allow_duplicate_awards')
        if allow_duplicate_awards is False and self.context.get('badgeclass') is not None:
            previous_awards = BadgeInstance.objects.filter(
                recipient_identifier=data['recipient_identifier'], badgeclass=self.context['badgeclass']
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__lt=timezone.now())
            )
            if previous_awards.exists():
                raise serializers.ValidationError(
                    "A previous award of this badge already exists for this recipient.")

        hashed = data.get('hashed', None)
        if hashed is None:
            if recipient_type in (RECIPIENT_TYPE_URL, RECIPIENT_TYPE_ID):
                data['hashed'] = False
            else:
                data['hashed'] = True

        return data

    def validate_narrative(self, data):
        if data is None or data == "":
            return None
        else:
            return data

    def to_representation(self, instance):
        representation = super(BadgeInstanceSerializerV1, self).to_representation(instance)
        representation['json'] = instance.get_json(obi_version="1_1", use_canonical_id=True)
        if self.context.get('include_issuer', False):
            representation['issuer'] = IssuerSerializerV1(instance.cached_badgeclass.cached_issuer).data
        else:
            representation['issuer'] = OriginSetting.HTTP + \
                reverse('issuer_json', kwargs={'entity_id': instance.cached_issuer.entity_id})
        if self.context.get('include_badge_class', False):
            representation['badge_class'] = BadgeClassSerializerV1(
                instance.cached_badgeclass, context=self.context).data
        else:
            representation['badge_class'] = OriginSetting.HTTP + \
                reverse('badgeclass_json', kwargs={'entity_id': instance.cached_badgeclass.entity_id})

        representation['public_url'] = OriginSetting.HTTP + \
            reverse('badgeinstance_json', kwargs={'entity_id': instance.entity_id})

        return representation

    def create(self, validated_data):
        """
        Requires self.context to include request (with authenticated request.user)
        and badgeclass: issuer.models.BadgeClass.
        """
        evidence_items = []

        # ob1 evidence url
        evidence_url = validated_data.get('evidence')
        if evidence_url:
            evidence_items.append({'evidence_url': evidence_url})

        # ob2 evidence items
        submitted_items = validated_data.get('evidence_items')
        if submitted_items:
            evidence_items.extend(submitted_items)
        try:
            return self.context.get('badgeclass').issue(
                recipient_id=validated_data.get('recipient_identifier'),
                narrative=validated_data.get('narrative'),
                evidence=evidence_items,
                notify=validated_data.get('create_notification'),
                created_by=self.context.get('request').user,
                allow_uppercase=validated_data.get('allow_uppercase'),
                recipient_type=validated_data.get('recipient_type', RECIPIENT_TYPE_EMAIL),
                badgr_app=BadgrApp.objects.get_current(self.context.get('request')),
                expires_at=validated_data.get('expires_at', None),
                extensions=validated_data.get('extension_items', None)
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message)

    def update(self, instance, validated_data):
        updateable_fields = [
            'evidence_items',
            'expires_at',
            'extension_items',
            'hashed',
            'narrative',
            'recipient_identifier',
            'recipient_type'
        ]

        for field_name in updateable_fields:
            if field_name in validated_data:
                setattr(instance, field_name, validated_data.get(field_name))
        instance.rebake(save=False)
        instance.save()

        return instance

class QrCodeSerializerV1(serializers.Serializer):
    title = serializers.CharField(max_length=254)
    slug = StripTagsCharField(max_length=255, source='entity_id', read_only=True)
    createdBy = serializers.CharField(max_length=254)
    badgeclass_id = serializers.CharField(max_length=254)
    issuer_id = serializers.CharField(max_length=254)
    request_count = serializers.SerializerMethodField()

    valid_from = DateTimeWithUtcZAtEndField(
        required=False, allow_null=True, default_timezone=pytz.utc
    )
    expires_at = DateTimeWithUtcZAtEndField(
        required=False, allow_null=True, default_timezone=pytz.utc
    )

    class Meta:
        apispec_definition = ('QrCode', {})

    def create(self, validated_data, **kwargs):
        title = validated_data.get('title')
        createdBy = validated_data.get('createdBy')
        badgeclass_id = validated_data.get('badgeclass_id')
        issuer_id = validated_data.get('issuer_id')

        try:
            issuer = Issuer.objects.get(entity_id=issuer_id)
        except Issuer.DoesNotExist:
            raise serializers.ValidationError(f"Issuer with ID '{issuer_id}' does not exist.")

        try:
            badgeclass = BadgeClass.objects.get(entity_id=badgeclass_id)
        except BadgeClass.DoesNotExist:
            raise serializers.ValidationError(f"BadgeClass with ID '{badgeclass_id}' does not exist.")

        new_qrcode = QrCode.objects.create(
            title=title,
            createdBy=createdBy,
            issuer=issuer,
            badgeclass=badgeclass,
            valid_from=validated_data.get('valid_from'),
            expires_at=validated_data.get('expires_at')
        )

        return new_qrcode

    def update(self, instance, validated_data):
        instance.title = validated_data.get('title', instance.title)
        instance.createdBy = validated_data.get('createdBy', instance.createdBy)
        instance.valid_from = validated_data.get('valid_from', instance.valid_from)
        instance.expires_at = validated_data.get('expires_at', instance.expires_at)
        instance.save()
        return instance
    
    def get_request_count(self, obj):
        return obj.requestedbadges.count()

   

class RequestedBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestedBadge
        fields = '__all__' 


class RequestedLearningPathSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestedLearningPath
        fields = '__all__' 

    def to_representation(self, instance):
        representation = super(RequestedLearningPathSerializer, self).to_representation(instance)
        representation["user"] = BadgeUserProfileSerializerV1(instance.user).data
        return representation    

class BadgeOrderSerializer(serializers.Serializer):
    slug = StripTagsCharField(max_length=255)
    order = serializers.IntegerField()
    
    class Meta:
        apispec_definition = ('LearningPathBadge', {})   

class LearningPathSerializerV1(serializers.Serializer):
    created_at = DateTimeWithUtcZAtEndField(read_only=True)
    updated_at = DateTimeWithUtcZAtEndField(read_only=True)
    issuer_id = serializers.CharField(max_length=254)
    participationBadge_id = serializers.CharField(max_length=254)
    participant_count = serializers.IntegerField(required=False, read_only=True, source='v1_api_participant_count')


    name = StripTagsCharField(max_length=255)
    slug = StripTagsCharField(max_length=255, read_only=True, source='entity_id')
    description = StripTagsCharField(max_length=16384, required=True, convert_null=True)

    tags = serializers.ListField(child=StripTagsCharField(max_length=1024), source='tag_items', required=False)
    badges = BadgeOrderSerializer(many=True, required=False)

    participationBadge_image = serializers.SerializerMethodField()


    class Meta:
        apispec_definition = ('LearningPath', {})

    def get_participationBadge_image(self, obj):
        return obj.participationBadge.image.url if obj.participationBadge.image else None 

    def get_participationBadge_id(self, obj):
        return obj.participationBadge.entity_id if obj.participationBadge.entity_id else None   

    def to_representation(self, instance):

        request = self.context.get('request')
        representation = super(LearningPathSerializerV1, self).to_representation(instance)  
        representation['issuer_name'] = instance.issuer.name
        representation['issuer_id']= instance.issuer.entity_id  
        representation['participationBadge_id'] = self.get_participationBadge_id(instance)
        representation['tags'] = list(instance.tag_items.values_list('name', flat=True))
        representation['badges'] = [
            {
                'badge': BadgeClassSerializerV1(badge.badge, context={'exclude_orgImg': 'extensions:OrgImageExtension'}).data,
                'order': badge.order,
            }
            for badge in instance.learningpathbadge_set.all().order_by('order')
        ]

        default_representation = {
            'progress': None,
            'completed_at': None,
            'completed_badges': None,
            'requested': False
        }
        if not request or not request.user.is_authenticated:
            representation.update(default_representation)
            return representation

        try:
            participant = LearningPathParticipant.objects.get(learning_path=instance, user=request.user)

            requested_lp_exists = RequestedLearningPath.objects.filter(learningpath=instance, user=request.user).exists()
            representation['requested'] = requested_lp_exists

            completed_badges = participant.completed_badges
            progress = sum(
                json_loads(ext.original_json)['StudyLoad'] 
                for badge in completed_badges 
                for ext in badge.cached_extensions() 
                if ext.name == 'extensions:StudyLoadExtension'
            )

            representation.update({
                'progress': progress,
                'completed_at': participant.completed_at,
                'completed_badges': BadgeClassSerializerV1(participant.completed_badges, many=True, context={'exclude_orgImg': 'extensions:OrgImageExtension'}).data,
            })

        except LearningPathParticipant.DoesNotExist:
            if request.user.is_authenticated: 
                user_badgeinstances = BadgeInstance.objects.filter(recipient_identifier=request.user.email, revoked=False)
                user_badgeclasses = [badge.badgeclass for badge in user_badgeinstances]
                completed_badgeclasses = {badge for badge in user_badgeclasses if badge in [badge.badge for badge in instance.learningpathbadge_set.all()]}
                completed_badges = BadgeClassSerializerV1(completed_badgeclasses, many=True, context={'exclude_orgImg': 'extensions:OrgImageExtension'}).data
                representation.update({
                    'progress': None,
                    'completed_at': None,
                    'completed_badges': completed_badges,
                    'requested': False
                })
            else: 
                representation.update(default_representation)   
        return representation          

    def create(self, validated_data, **kwargs):
        
        name = validated_data.get('name')
        description = validated_data.get('description')
        tags = validated_data.get('tag_items')
        issuer_id = validated_data.get('issuer_id')
        participationBadge_id = validated_data.get('participationBadge_id')
        badges_data = validated_data.get('badges') 

        try:
            issuer = Issuer.objects.get(entity_id=issuer_id)
        except Issuer.DoesNotExist:
            raise serializers.ValidationError(f"Issuer with ID '{issuer_id}' does not exist.")
        
        try:
            participationBadge = BadgeClass.objects.get(entity_id=participationBadge_id)
        except BadgeClass.DoesNotExist:
            raise serializers.ValidationError(f" with ID '{participationBadge_id}' does not exist.")
        

        badges_with_order = []
        for badge_data in badges_data:
            slug = badge_data.get('slug')
            order = badge_data.get('order')

            try:
                badge = BadgeClass.objects.get(entity_id=slug)
            except BadgeClass.DoesNotExist:
                raise serializers.ValidationError(f"Badge with slug '{slug}' does not exist.")

            badges_with_order.append((badge, order))

        new_learningpath = LearningPath.objects.create(
            name=name,
            description=description,
            issuer=issuer,
            participationBadge=participationBadge
        )
        new_learningpath.tag_items = tags


        new_learningpath.learningpath_badges = badges_with_order
        return new_learningpath
    
    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        
        tags = validated_data.get('tag_items', None)
        if tags is not None:
            instance.tag_items = tags

        badges_data = validated_data.get('badges', None)
        if badges_data is not None:
            badges_with_order = []
            for badge_data in badges_data:
                slug = badge_data.get('slug')
                order = badge_data.get('order')

                try:
                    badge = BadgeClass.objects.get(entity_id=slug)
                except BadgeClass.DoesNotExist:
                    raise serializers.ValidationError(f"Badge with slug '{slug}' does not exist.")

                badges_with_order.append((badge, order))

            instance.learningpath_badges = badges_with_order

        instance.save()

        return instance

class LearningPathParticipantSerializerV1(serializers.ModelSerializer):
    user = BadgeUserProfileSerializerV1(source='cached_user')
    completed_badges = BadgeClassSerializerV1(many=True, read_only=True)
    participationBadgeAssertion = BadgeInstanceSerializerV1(read_only=True)
    
    class Meta:
        model = LearningPathParticipant
        fields = ['user', 'started_at', 'completed_at', 'completed_badges', 'entity_id', 'participationBadgeAssertion']
