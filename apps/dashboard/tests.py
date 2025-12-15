# encoding: utf-8
"""
Dashboard tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class DashboardAPITests(TestCase):
    """Test dashboard API endpoints"""

    def setUp(self):
        """Set up test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_kpis_endpoint_requires_auth(self):
        """Test that KPIs endpoint requires authentication"""
        client = APIClient()
        response = client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_kpis_endpoint_returns_data(self):
        """Test that authenticated user can access KPIs"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('topKpis', response.data)
        self.assertIn('secondaryKpis', response.data)

    def test_competency_areas_endpoint(self):
        """Test competency areas list endpoint"""
        response = self.client.get('/v1/dashboard/overview/competency-areas')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('data', response.data)

    def test_competency_area_detail_endpoint(self):
        """Test competency area detail endpoint"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital')
        # Will return 404 if no data, or 200 if data exists
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_top_badges_endpoint(self):
        """Test top badges endpoint"""
        response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('badges', response.data)

    def test_top_badges_with_limit(self):
        """Test top badges endpoint with limit parameter"""
        response = self.client.get('/v1/dashboard/overview/top-badges?limit=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        badges = response.data.get('badges', [])
        self.assertLessEqual(len(badges), 5)


class NetworkDashboardAPITests(TestCase):
    """Test network dashboard API endpoints"""

    def setUp(self):
        """Set up test client, user, network, and issuers"""
        from issuer.models import Issuer, NetworkMembership, BadgeClass, BadgeInstance
        from allauth.account.models import EmailAddress

        self.client = APIClient()

        # Create a test user
        self.user = User.objects.create_user(
            username='networkuser',
            email='networkuser@example.com',
            password='testpass123'
        )

        # Verify email for the user
        EmailAddress.objects.create(
            user=self.user,
            email='networkuser@example.com',
            verified=True,
            primary=True
        )

        self.client.force_authenticate(user=self.user)

        # Create a network (Issuer with is_network=True)
        self.network = Issuer.objects.create(
            name='Test Network',
            description='A test network',
            email='network@test.com',
            url='https://test-network.com',
            is_network=True,
            created_by=self.user,
            verified=True
        )

        # Create an issuer in the network
        self.issuer = Issuer.objects.create(
            name='Test Issuer',
            description='A test issuer',
            email='issuer@test.com',
            url='https://test-issuer.com',
            is_network=False,
            created_by=self.user,
            verified=True
        )

        # Add issuer to network
        NetworkMembership.objects.create(
            network=self.network,
            issuer=self.issuer
        )

        # Create a badge class
        self.badge_class = BadgeClass.objects.create(
            name='Test Badge',
            description='A test badge',
            issuer=self.issuer,
            created_by=self.user
        )

        # Create badge instances
        for i in range(5):
            BadgeInstance.objects.create(
                badgeclass=self.badge_class,
                issuer=self.issuer,
                recipient_identifier=f'user{i}@test.com',
                created_by=self.user
            )

    def test_network_kpis_endpoint_requires_auth(self):
        """Test that network KPIs endpoint requires authentication"""
        client = APIClient()
        response = client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_network_kpis_endpoint_returns_data(self):
        """Test that authenticated user can access network KPIs"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('kpis', response.data)

        # Verify KPI structure
        kpis = response.data['kpis']
        self.assertIsInstance(kpis, list)
        self.assertGreater(len(kpis), 0)

        # Check that expected KPI IDs are present
        kpi_ids = [kpi['id'] for kpi in kpis]
        expected_ids = [
            'institutions_count',
            'badges_created',
            'badges_awarded',
            'participation_badges',
            'competency_badges',
            'competency_hours',
            'learners_count',
            'badges_per_month',
            'learners_with_paths',
        ]
        for expected_id in expected_ids:
            self.assertIn(expected_id, kpi_ids)

    def test_network_kpis_returns_correct_counts(self):
        """Test that KPIs return correct counts"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi['value'] for kpi in response.data['kpis']}

        # Check institutions count (1 issuer in network)
        self.assertEqual(kpis['institutions_count'], 1)

        # Check badges created (1 badge class)
        self.assertEqual(kpis['badges_created'], 1)

        # Check badges awarded (5 badge instances)
        self.assertEqual(kpis['badges_awarded'], 5)

    def test_network_kpis_invalid_network(self):
        """Test 404 for non-existent network"""
        response = self.client.get(
            '/v1/issuer/networks/nonexistent-network/dashboard/kpis'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_network_competency_areas_endpoint(self):
        """Test network competency areas endpoint"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('data', response.data)

    def test_network_competency_areas_with_limit(self):
        """Test network competency areas with limit parameter"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas?limit=3'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('data', [])
        self.assertLessEqual(len(data), 3)

    def test_network_top_badges_endpoint(self):
        """Test network top badges endpoint"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('badges', response.data)

        # Check that badges are returned
        badges = response.data['badges']
        self.assertIsInstance(badges, list)

        # With our test data, we should have at least one badge
        if len(badges) > 0:
            first_badge = badges[0]
            self.assertIn('rank', first_badge)
            self.assertIn('badgeId', first_badge)
            self.assertIn('badgeTitle', first_badge)
            self.assertIn('count', first_badge)

    def test_network_top_badges_with_limit(self):
        """Test network top badges with limit parameter"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges?limit=5'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        badges = response.data.get('badges', [])
        self.assertLessEqual(len(badges), 5)

    def test_network_top_badges_metadata(self):
        """Test that top badges metadata includes total count"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        metadata = response.data.get('metadata', {})
        self.assertIn('totalBadges', metadata)
        self.assertEqual(metadata['totalBadges'], 5)  # 5 badge instances
        self.assertIn('lastUpdated', metadata)

    def test_network_dashboard_issuer_not_network(self):
        """Test 404 when trying to access dashboard for a regular issuer"""
        response = self.client.get(
            f'/v1/issuer/networks/{self.issuer.entity_id}/dashboard/kpis'
        )
        # Should return 404 because issuer is not a network
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
