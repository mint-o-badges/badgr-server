from badgeuser.models import BadgeUser, CachedEmailAddress
from issuer.models import BadgeClass, Issuer, BadgeInstance
from mainsite.tests.base import BadgrTestCase

from backpack.models import BackpackCollection, BackpackCollectionBadgeInstance
from backpack.serializers_v1 import CollectionSerializerV1
from backpack.serializers_v2 import BackpackCollectionSerializerV2


class TestCollections(BadgrTestCase):
    def setUp(self):
        super(TestCollections, self).setUp()
        self.user, _ = BadgeUser.objects.get_or_create(email='test@example.com')

        self.cached_email, _ = CachedEmailAddress.objects.get_or_create(user=self.user,
                email='test@example.com', verified=True, primary=True)

        self.issuer = Issuer.objects.create(
            name="Open Badges",
            created_at="2015-12-15T15:55:51Z",
            created_by=None,
            slug="open-badges",
            source_url="http://badger.openbadges.org/program/meta/bda68a0b505bc0c7cf21bc7900280ee74845f693",
            source="test-fixture",
            image=""
        )

        self.badge_class = BadgeClass.objects.create(
            name="MozFest Reveler",
            created_at="2015-12-15T15:55:51Z",
            created_by=None,
            slug="mozfest-reveler",
            criteria_text=None,
            source_url="http://badger.openbadges.org/badge/meta/mozfest-reveler",
            source="test-fixture",
            image="",
            issuer=self.issuer
        )

        self.local_badge_instance_1 = BadgeInstance.objects.create(
            recipient_identifier="test@example.com",
            badgeclass=self.badge_class,
            issuer=self.issuer,
            image="uploads/badges/local_badgeinstance_174e70bf-b7a8-4b71-8125-c34d1a994a7c.png",
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        self.local_badge_instance_2 = BadgeInstance.objects.create(
            recipient_identifier="test@example.com",
            badgeclass=self.badge_class,
            issuer=self.issuer,
            image="uploads/badges/local_badgeinstance_174e70bf-b7a8-4b71-8125-c34d1a994a7c.png",
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        self.local_badge_instance_3 = BadgeInstance.objects.create(
            recipient_identifier="test@example.com",
            badgeclass=self.badge_class,
            issuer=self.issuer,
            image="uploads/badges/local_badgeinstance_174e70bf-b7a8-4b71-8125-c34d1a994a7c.png",
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        self.collection = BackpackCollection.objects.create(
            created_by=self.user,
            description='The Freshest Ones',
            name='Fresh Badges',
            slug='fresh-badges'
        )

        BackpackCollection.objects.create(
            created_by=self.user,
            description='It\'s even fresher.',
            name='Cool New Collection',
            slug='cool-new-collection'
        )
        BackpackCollection.objects.create(
            created_by=self.user,
            description='Newest!',
            name='New collection',
            slug='new-collection'
        )

    def test_can_get_collection_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/v1/earner/collections')
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['badges'], [])

    def test_can_get_collection_detail(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/v1/earner/collections/fresh-badges')

        self.assertEqual(response.data['badges'], [])

        response = self.client.get('/v2/backpack/collections/{}'.format(self.collection.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['result'][0]['shareHash'], '')
        self.assertEqual(response.data['result'][0]['owner'], self.user.entity_id)

        self.collection.published = True
        self.collection.save()

        response = self.client.get('/v2/backpack/collections/{}'.format(self.collection.entity_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['result'][0]['shareHash'], self.collection.share_hash)

    def test_can_define_collection(self):
        """
        Authorized user can create a new collection via API.
        """
        data = {
            'name': 'Fruity Collection',
            'description': 'Apples and Oranges',
            'published': True,
            'badges': [
                {'id': self.local_badge_instance_1.entity_id},
                {'id': self.local_badge_instance_2.entity_id, 'description': 'A cool badge'}
            ]
        }
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/v1/earner/collections', data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data.get('published'))

        self.assertEqual([i['id'] for i in response.data.get('badges')],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

    def test_can_define_collection_serializer(self):
        """
        A new collection may be created directly via serializer.
        """
        data = {
            'name': 'Fruity Collection',
            'description': 'Apples and Oranges',
            'badges': [{'id': self.local_badge_instance_1.entity_id},
                {'id': self.local_badge_instance_2.entity_id, 'description': 'A cool badge'}]
        }

        serializer = CollectionSerializerV1(data=data, context={'user': self.user})
        serializer.is_valid(raise_exception=True)
        collection = serializer.save()

        self.assertIsNotNone(collection.pk)
        self.assertEqual(collection.name, data['name'])
        self.assertEqual(collection.cached_badgeinstances().count(), 2)

    def test_can_delete_collection(self):
        """
        Authorized user may delete one of their defined collections.
        """
        collection = BackpackCollection.objects.filter(created_by_id=self.user.id).first()

        self.client.force_authenticate(user=self.user)
        response = self.client.delete('/v1/earner/collections/{}'.format(collection.entity_id))

        self.assertEqual(response.status_code, 204)

    def test_can_publish_unpublish_collection_serializer(self):
        """
        The CollectionSerializer should be able to update/delete a collection's share hash
        via update method.
        """
        collection = BackpackCollection.objects.first()
        self.assertIn(collection.share_url, ('', None))

        serializer = CollectionSerializerV1(
            collection,
            data={'published': True}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertNotEqual(collection.share_url, '')
        self.assertTrue(collection.published)

        serializer = CollectionSerializerV1(
            collection,
            data={'published': False}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertFalse(collection.published)
        self.assertIn(collection.share_url, ('', None))

    def test_can_publish_unpublish_collection_api_share_method(self):
        """
        The CollectionSerializer should be able to update/delete a collection's share hash
        via the CollectionGenerateShare GET/DELETE methods.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            '/v1/earner/collections/fresh-badges/share'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith('http'))

        collection = BackpackCollection.objects.get(pk=self.collection.pk)

        self.assertTrue(collection.published)

        response = self.client.delete('/v1/earner/collections/fresh-badges/share')
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.data)

        self.assertFalse(self.collection.published)

    def test_can_add_remove_collection_badges_via_serializer_v1(self):
        """
        The CollectionSerializer should be able to update an existing collection's badge list
        """
        collection = BackpackCollection.objects.first()
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        serializer = CollectionSerializerV1(
            collection,
            data={'badges': [{'id': self.local_badge_instance_1.entity_id},
                {'id': self.local_badge_instance_2.entity_id}]},
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        serializer = CollectionSerializerV1(
            collection,
            data={'badges': [{'id': self.local_badge_instance_2.entity_id},
                {'id': self.local_badge_instance_3.entity_id}]},
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])

    def test_can_add_remove_collection_badges_via_serializer_v2(self):
        """
        The BackpackCollectionSerializerV2 should be able to update an existing collection's badge list
        """
        collection = BackpackCollection.objects.first()
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        serializer = BackpackCollectionSerializerV2(
            collection,
            data={'assertions': [self.local_badge_instance_1.entity_id,
                self.local_badge_instance_2.entity_id]},
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        serializer = BackpackCollectionSerializerV2(
            collection,
            data={'assertions': [self.local_badge_instance_2.entity_id,
                self.local_badge_instance_3.entity_id]},
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])

    def test_can_add_remove_collection_badges_via_collection_detail_api(self):
        """
        A PUT request to the CollectionDetail view should be able to update the list of badges
        in a collection.
        """
        collection = BackpackCollection.objects.first()
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        data = {
            'badges': [{'id': self.local_badge_instance_1.entity_id},
                {'id': self.local_badge_instance_2.entity_id}],
            'name': collection.name,
            'description': collection.description
        }
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            '/v1/earner/collections/{}'.format(collection.entity_id), data=data,
            format='json')

        self.assertEqual(response.status_code, 200)
        collection = BackpackCollection.objects.get(entity_id=response.data.get('slug'))  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        data = {
            'badges': [{'id': self.local_badge_instance_2.entity_id},
                {'id': self.local_badge_instance_3.entity_id}],
            'name': collection.name,
        }
        response = self.client.put(
            '/v1/earner/collections/{}'.format(collection.entity_id),
            data=data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([i['id'] for i in response.data.get('badges')],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])
        collection = BackpackCollection.objects.get(entity_id=response.data.get('slug'))  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])

    def test_can_add_remove_badges_via_collection_badge_detail_api(self):
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        data = [{'id': self.local_badge_instance_1.entity_id},
                {'id': self.local_badge_instance_2.entity_id}]

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/v1/earner/collections/{}/badges'.format(self.collection.entity_id), data=data,
            format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual([i['id'] for i in response.data],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        collection = BackpackCollection.objects.first()  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        response = self.client.get('/v1/earner/collections/{}/badges'.format(collection.slug))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        response = self.client.delete(
            '/v1/earner/collections/{}/badges/{}'.format(collection.entity_id, data[0]['id']),
            data=data, format='json')

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.data)
        collection = BackpackCollection.objects.first()  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 1)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_2.entity_id])

    def test_can_add_remove_issuer_badges_via_api(self):
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        data = [
            {'id': self.local_badge_instance_1.entity_id},
            {'id': self.local_badge_instance_2.entity_id}
        ]

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/v1/earner/collections/{}/badges'.format(self.collection.entity_id), data=data,
            format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual([i['id'] for i in response.data],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        self.assertEqual(self.collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in self.collection.cached_badgeinstances()],
                [self.local_badge_instance_1.entity_id, self.local_badge_instance_2.entity_id])

        response = self.client.get(
            '/v1/earner/collections/{}/badges/{}'.format(self.collection.entity_id,
                self.local_badge_instance_2.entity_id)
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.delete(
            '/v1/earner/collections/{}/badges/{}'.format(self.collection.entity_id,
                self.local_badge_instance_2.entity_id)
        )
        self.assertEqual(response.status_code, 204)

    def test_api_handles_null_description_and_adds_badge(self):
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        data = {
            'badges': [{'id': self.local_badge_instance_1.entity_id, 'description': None}],
            'name': self.collection.name,
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            '/v1/earner/collections/{}'.format(self.collection.entity_id), data=data,
            format='json')
        self.assertEqual(response.status_code, 200)

        entry = self.collection.cached_collects().first()
        self.assertEqual(entry.badgeinstance_id, self.local_badge_instance_1.pk)

    def test_can_add_remove_collection_badges_collection_badgelist_api(self):
        """
        A PUT request to the Collection BadgeList endpoint should update the list of badges
        n a collection
        """
        self.assertEqual(len(self.collection.cached_badgeinstances()), 0)

        data = [{'id': self.local_badge_instance_1.entity_id}, {'id': self.local_badge_instance_2.entity_id}]

        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            '/v1/earner/collections/{}/badges'.format(self.collection.entity_id), data=data,
            format='json')

        self.assertEqual(response.status_code, 200)
        collection = BackpackCollection.objects.first()  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.pk for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_1.pk, self.local_badge_instance_2.pk])

        data = [{'id': self.local_badge_instance_2.entity_id}, {'id': self.local_badge_instance_3.entity_id}]
        response = self.client.put(
            '/v1/earner/collections/{}/badges'.format(collection.entity_id),
            data=data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([i['id'] for i in response.data],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])
        collection = BackpackCollection.objects.first()  # reload
        self.assertEqual(collection.cached_badgeinstances().count(), 2)
        self.assertEqual([i.entity_id for i in collection.cached_badgeinstances()],
                [self.local_badge_instance_2.entity_id, self.local_badge_instance_3.entity_id])

    def xit_test_can_update_badge_description_in_collection_via_detail_api(self):
        self.assertEqual(self.collection.cached_badgeinstances().count(), 0)

        serializer = CollectionSerializerV1(
            self.collection,
            data={'badges': [{'id': self.local_badge_instance_1.pk},
                             {'id': self.local_badge_instance_2.pk}]},
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(self.collection.cached_badgeinstances().count(), 2)

        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            '/v1/earner/collections/{}/badges/{}'.format(self.collection.entity_id,
                self.local_badge_instance_1.pk),
            data={'id': 1, 'description': 'A cool badge.'}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'id': self.local_badge_instance_1.pk, 'description': 'A cool badge.'})

        obj = BackpackCollectionBadgeInstance.objects.get(collection=self.collection,
                instance_id=self.local_badge_instance_1.pk)
        self.assertEqual(obj.description, 'A cool badge.')

    def test_badge_share_json(self):
        """
        Legacy Badge Share pages should redirect to public pages
        """
        response = self.client.get('/share/badge/{}'.format(self.local_badge_instance_1.pk), **dict(
            HTTP_ACCEPT="application/json"
        ))

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.get('Location', None), self.local_badge_instance_1.public_url)

    def test_badge_share_html(self):
        """
        Legacy Badge Share pages should redirect to public pages
        """
        response = self.client.get('/share/badge/{}'.format(self.local_badge_instance_1.entity_id), **dict(
            HTTP_ACCEPT='text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        ))

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.get('Location', None), self.local_badge_instance_1.public_url)
