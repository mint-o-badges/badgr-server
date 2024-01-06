# encoding: utf-8

import os
import binascii
from collections import OrderedDict

import cachemodel
from basic_models.models import CreatedUpdatedAt
from django.urls import reverse
from django.db import models, transaction
from django.db.models import Q

from entity.models import BaseVersionedEntity
from issuer.models import BaseAuditedModelDeletedWithUser, BadgeInstance
from backpack.sharing import SharingManager
from issuer.utils import CURRENT_OBI_VERSION, get_obi_context, add_obi_version_ifneeded
from mainsite.managers import SlugOrJsonIdCacheModelManager
from mainsite.models import BadgrApp
from mainsite.utils import OriginSetting


class BackpackCollection(BaseAuditedModelDeletedWithUser, BaseVersionedEntity):
    entity_class_name = 'BackpackCollection'
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=255, blank=True)
    share_hash = models.CharField(max_length=255, null=False, blank=True)

    # slug has been deprecated, but keep for legacy collections redirects
    slug = models.CharField(max_length=254, blank=True, null=True, default=None)

    assertions = models.ManyToManyField('issuer.BadgeInstance', blank=True,
            through='backpack.BackpackCollectionBadgeInstance')

    cached = SlugOrJsonIdCacheModelManager(slug_kwarg_name='entity_id', slug_field_name='entity_id')

    def publish(self):
        super(BackpackCollection, self).publish()
        self.publish_by('share_hash')
        self.created_by.publish()

    def delete(self, *args, **kwargs):
        super(BackpackCollection, self).delete(*args, **kwargs)
        self.publish_delete('share_hash')
        self.created_by.publish()

    def save(self, **kwargs):
        if self.pk:
            BackpackCollectionBadgeInstance.objects.filter(
                Q(badgeinstance__acceptance=BadgeInstance.ACCEPTANCE_REJECTED) | Q(badgeinstance__revoked=True)
            ).delete()
        super(BackpackCollection, self).save(**kwargs)

    @cachemodel.cached_method(auto_publish=True)
    def cached_badgeinstances(self):
        return self.assertions.filter(
            revoked=False,
            acceptance__in=(BadgeInstance.ACCEPTANCE_ACCEPTED, BadgeInstance.ACCEPTANCE_UNACCEPTED)
        )

    @cachemodel.cached_method(auto_publish=True)
    def cached_collects(self):
        return self.backpackcollectionbadgeinstance_set.filter(
            badgeinstance__revoked=False,
            badgeinstance__acceptance__in=(BadgeInstance.ACCEPTANCE_ACCEPTED,
                BadgeInstance.ACCEPTANCE_UNACCEPTED)
        )

    @property
    def owner(self):
        from badgeuser.models import BadgeUser
        return BadgeUser.cached.get(id=self.created_by_id)

    # Convenience methods for toggling published state
    @property
    def published(self):
        return bool(self.share_hash)

    @published.setter
    def published(self, value):
        if value and not self.share_hash:
            self.share_hash = str(binascii.hexlify(os.urandom(16)), 'utf-8')
        elif not value and self.share_hash:
            self.publish_delete('share_hash')
            self.share_hash = ''

    @property
    def share_url(self):
        if self.published:
            return OriginSetting.HTTP + reverse('collection_json', kwargs={'entity_id': self.share_hash})

    def get_share_url(self, **kwargs):
        return self.share_url

    @property
    def badge_items(self):
        return self.cached_badgeinstances()

    @badge_items.setter
    def badge_items(self, value):
        """
        Update this collection's list of BackpackCollectionBadgeInstance
        from a list of BadgeInstance EntityRelatedFieldV2 serializer data
        :param value: list of BadgeInstance instances or list of
        BadgeInstance entity_id strings.
        """
        def _is_in_requested_badges(entity_id):
            if entity_id in value:
                return True
            try:
                if entity_id in [i.entity_id for i in value]:
                    return True
            except AttributeError:
                pass
            return False

        with transaction.atomic():
            existing_badges = {b.entity_id: b for b in self.badge_items}
            # add missing badges
            for badge_reference in value:
                try:
                    if isinstance(badge_reference, BadgeInstance):
                        badgeinstance = badge_reference
                    else:
                        badgeinstance = BadgeInstance.cached.get(entity_id=badge_reference)
                except BadgeInstance.DoesNotExist:
                    pass
                else:
                    if badgeinstance.entity_id not in list(existing_badges.keys()):
                        BackpackCollectionBadgeInstance.cached.get_or_create(
                            collection=self,
                            badgeinstance=badgeinstance
                        )

            # remove badges no longer in collection
            for badge_entity_id, badgeinstance in list(existing_badges.items()):
                if not _is_in_requested_badges(badge_entity_id):
                    BackpackCollectionBadgeInstance.objects.filter(
                        collection=self,
                        badgeinstance=badgeinstance
                    ).delete()

    def get_json(self, obi_version=CURRENT_OBI_VERSION, expand_badgeclass=False,
            expand_issuer=False, include_extra=True):
        obi_version, context_iri = get_obi_context(obi_version)

        json = OrderedDict([
            ('@context', context_iri),
            ('type', 'Collection'),
            ('id', add_obi_version_ifneeded(self.share_url, obi_version)),
            ('name', self.name),
            ('description', self.description),
            ('entityId', self.entity_id),
            ('owner', OrderedDict([
                ('firstName', self.cached_creator.first_name),
                ('lastName', self.cached_creator.last_name),
            ]))
        ])
        json['badges'] = [b.get_json(obi_version=obi_version,
                                     expand_badgeclass=expand_badgeclass,
                                     expand_issuer=expand_issuer,
                                     include_extra=include_extra) for b in self.cached_badgeinstances()]

        return json

    @property
    def cached_badgrapp(self):
        creator = self.cached_creator
        if creator and creator.badgrapp_id:
            return BadgrApp.objects.get(pk=creator.badgrapp_id)
        return BadgrApp.objects.get_current(None)


class BackpackCollectionBadgeInstance(cachemodel.CacheModel):
    collection = models.ForeignKey('backpack.BackpackCollection',
                                   on_delete=models.CASCADE)
    badgeuser = models.ForeignKey('badgeuser.BadgeUser', null=True, default=None,
                                  on_delete=models.CASCADE)
    badgeinstance = models.ForeignKey('issuer.BadgeInstance',
                                      on_delete=models.CASCADE)

    def publish(self):
        super(BackpackCollectionBadgeInstance, self).publish()
        self.collection.publish()

    def delete(self):
        super(BackpackCollectionBadgeInstance, self).delete()
        self.collection.publish()

    @property
    def cached_badgeinstance(self):
        return BadgeInstance.cached.get(id=self.badgeinstance_id)

    @property
    def cached_collection(self):
        return BackpackCollection.cached.get(id=self.collection_id)


class BaseSharedModel(cachemodel.CacheModel, CreatedUpdatedAt):
    SHARE_PROVIDERS = [(p.provider_code, p.provider_name)
            for code, p in list(SharingManager.ManagerProviders.items())]
    provider = models.CharField(max_length=254, choices=SHARE_PROVIDERS)
    source = models.CharField(max_length=254, default="unknown")

    class Meta:
        abstract = True

    def get_share_url(self, provider, **kwargs):
        raise NotImplementedError()


class BackpackBadgeShare(BaseSharedModel):
    badgeinstance = models.ForeignKey("issuer.BadgeInstance", null=True,
                                      on_delete=models.CASCADE)

    def get_share_url(self, provider, **kwargs):
        return SharingManager.share_url(provider, self.badgeinstance, **kwargs)


class BackpackCollectionShare(BaseSharedModel):
    collection = models.ForeignKey('backpack.BackpackCollection', null=False,
                                   on_delete=models.CASCADE)

    def get_share_url(self, provider, **kwargs):
        return SharingManager.share_url(provider, self.collection, **kwargs)
