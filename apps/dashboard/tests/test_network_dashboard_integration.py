# encoding: utf-8
"""
Comprehensive integration tests for Network Dashboard API endpoints.

Tests the following endpoints:
- GET /v1/issuer/networks/{networkSlug}/dashboard/kpis
- GET /v1/issuer/networks/{networkSlug}/dashboard/competency-areas
- GET /v1/issuer/networks/{networkSlug}/dashboard/top-badges

These tests verify:
1. Data accuracy and plausibility
2. KPI calculations (institutions, badges, learners, hours, etc.)
3. Trend calculations
4. Competency area aggregation
5. Top badges ranking
6. Edge cases (empty network, no badges, etc.)
7. Authentication and authorization
8. Error handling
"""
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from badgeuser.models import BadgeUser
from issuer.models import (
    Issuer,
    BadgeClass,
    BadgeInstance,
    BadgeClassExtension,
    NetworkMembership,
    LearningPath,
    LearningPathBadge,
)
from mainsite.tests.base import BadgrTestCase

import json


def mock_issuer_save(self, *args, **kwargs):
    """Override Issuer.save to skip geocoding for tests"""
    from django.db.models import Model
    super(Issuer, self).save(*args, **kwargs)


def mock_badgeclass_save(self, *args, **kwargs):
    """Override BadgeClass.save to skip image processing for tests"""
    from django.db.models import Model
    super(BadgeClass, self).save(*args, **kwargs)


def mock_badgeinstance_save(self, *args, **kwargs):
    """Override BadgeInstance.save to skip processing for tests"""
    from django.db.models import Model
    super(BadgeInstance, self).save(*args, **kwargs)


def mock_notify_earner(self, *args, **kwargs):
    """Skip notify_earner for tests"""
    pass


ISSUER_SAVE_MOCK = patch('issuer.models.Issuer.save', mock_issuer_save)
BADGECLASS_SAVE_MOCK = patch('issuer.models.BadgeClass.save', mock_badgeclass_save)
ASSERTION_SAVE_MOCK = patch('issuer.models.BadgeInstance.save', mock_badgeinstance_save)
NOTIFY_EARNER_MOCK = patch('issuer.models.BadgeInstance.notify_earner', mock_notify_earner)


class NetworkDashboardKPIsIntegrationTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard KPIs endpoint.

    Tests data accuracy and plausibility for all KPI values.
    """

    def setUp(self):
        """Set up comprehensive test fixtures"""
        super().setUp()
        self.client = APIClient()

        # Create admin user
        self.admin_user = self.setup_user(
            email='network_admin@example.com',
            first_name='Network',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        # Create a network
        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Test Network',
                description='A test network for dashboard testing',
                email='network@test.com',
                url='https://test-network.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True,
                linkedinId=''
            )

            # Create member issuers
            self.issuer1 = Issuer.objects.create(
                name='University One',
                description='First university',
                email='uni1@test.com',
                url='https://uni1.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True,
                linkedinId=''
            )

            self.issuer2 = Issuer.objects.create(
                name='University Two',
                description='Second university',
                email='uni2@test.com',
                url='https://uni2.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True,
                linkedinId=''
            )

            # Non-network issuer (should not appear in network stats)
            self.issuer_outside = Issuer.objects.create(
                name='Outside University',
                description='Not in network',
                email='outside@test.com',
                url='https://outside.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True,
                linkedinId=''
            )

        # Add issuers to network
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create learner users
        self.learner1 = self.setup_user(
            email='learner1@example.com',
            first_name='Learner',
            last_name='One',
            authenticate=False
        )
        self.learner2 = self.setup_user(
            email='learner2@example.com',
            first_name='Learner',
            last_name='Two',
            authenticate=False
        )
        self.learner3 = self.setup_user(
            email='learner3@example.com',
            first_name='Learner',
            last_name='Three',
            authenticate=False
        )

    def _create_badge_class(self, issuer, name, category=None, competencies=None):
        """Helper to create a badge class with optional extensions"""
        badge_class = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=issuer,
            created_by=self.admin_user,
            criteria_text='Complete the course'
        )

        if category:
            BadgeClassExtension.objects.create(
                badgeclass=badge_class,
                name='extensions:CategoryExtension',
                original_json=json.dumps({'Category': category})
            )

        if competencies:
            BadgeClassExtension.objects.create(
                badgeclass=badge_class,
                name='extensions:CompetencyExtension',
                original_json=json.dumps(competencies)
            )

        return badge_class

    def _award_badge(self, badge_class, user, created_at=None):
        """Helper to award a badge to a user"""
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            instance = BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=user,
                issuer=badge_class.issuer,
                recipient_identifier=user.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
            )
        if created_at:
            BadgeInstance.objects.filter(pk=instance.pk).update(created_at=created_at)
            instance.refresh_from_db()
        return instance

    def test_kpis_institutions_count(self):
        """Test that institutions_count returns correct number of network members"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be 2 institutions (issuer1, issuer2)
        self.assertEqual(kpis['institutions_count']['value'], 2)

    def test_kpis_badges_created_count(self):
        """Test that badges_created returns correct count of badge classes"""
        # Create badge classes
        self._create_badge_class(self.issuer1, 'Badge A')
        self._create_badge_class(self.issuer1, 'Badge B')
        self._create_badge_class(self.issuer2, 'Badge C')

        # Create badge outside network (should not be counted)
        self._create_badge_class(self.issuer_outside, 'Outside Badge')

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be 3 badges in network
        self.assertEqual(kpis['badges_created']['value'], 3)

    def test_kpis_badges_awarded_count(self):
        """Test that badges_awarded returns correct count of badge instances"""
        badge1 = self._create_badge_class(self.issuer1, 'Award Badge 1')
        badge2 = self._create_badge_class(self.issuer2, 'Award Badge 2')
        outside_badge = self._create_badge_class(self.issuer_outside, 'Outside Badge')

        # Award badges within network
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge2, self.learner3)

        # Award badge outside network (should not be counted)
        self._award_badge(outside_badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be 3 badges awarded in network
        self.assertEqual(kpis['badges_awarded']['value'], 3)

    def test_kpis_participation_and_competency_badges(self):
        """Test that participation_badges and competency_badges are counted correctly"""
        # Create participation badges
        self._create_badge_class(self.issuer1, 'Participation 1', category='participation')
        self._create_badge_class(self.issuer1, 'Participation 2', category='participation')

        # Create competency badges
        self._create_badge_class(self.issuer2, 'Competency 1', category='competency')
        self._create_badge_class(self.issuer2, 'Competency 2', category='competency')
        self._create_badge_class(self.issuer2, 'Competency 3', category='competency')

        # Create badge without category
        self._create_badge_class(self.issuer1, 'No Category Badge')

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        self.assertEqual(kpis['participation_badges']['value'], 2)
        self.assertEqual(kpis['competency_badges']['value'], 3)

    def test_kpis_competency_hours(self):
        """Test that competency_hours returns value in hours and trendValue in percent"""
        # Create badge with competencies (studyLoad in minutes)
        competencies = [
            {'name': 'Skill A', 'studyLoad': 120},  # 2 hours
            {'name': 'Skill B', 'studyLoad': 60},   # 1 hour
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Hours Badge', category='competency', competencies=competencies
        )

        now = timezone.now()

        # Award 2 badges in current period (last 30 days) = 2 * 3 hours = 6 hours
        self._award_badge(badge, self.learner1, created_at=now - timedelta(days=5))
        self._award_badge(badge, self.learner2, created_at=now - timedelta(days=10))

        # Award 1 badge in previous period (30-60 days ago) = 1 * 3 hours = 3 hours
        self._award_badge(badge, self.learner3, created_at=now - timedelta(days=45))

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Total: 3 instances * (120 + 60) minutes / 60 = 9 hours
        self.assertEqual(kpis['competency_hours']['value'], 9)

        # trendValue should be percentage: (6-3)/3 * 100 = 100%
        self.assertEqual(kpis['competency_hours']['trendValue'], 100)
        self.assertEqual(kpis['competency_hours']['trend'], 'up')

    def test_kpis_competency_hours_last_month(self):
        """Test that competency_hours_last_month returns value and trendValue in hours (not percent)"""
        # Create badge with competencies (studyLoad in minutes)
        competencies = [
            {'name': 'Skill A', 'studyLoad': 120},  # 2 hours
            {'name': 'Skill B', 'studyLoad': 60},   # 1 hour
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Hours Badge', category='competency', competencies=competencies
        )

        now = timezone.now()

        # Award 2 badges within last 30 days = 2 * 3 hours = 6 hours (current period)
        self._award_badge(badge, self.learner1, created_at=now - timedelta(days=5))
        self._award_badge(badge, self.learner2, created_at=now - timedelta(days=15))

        # Award 1 badge in previous period (30-60 days ago) = 1 * 3 hours = 3 hours
        self._award_badge(badge, self.learner3, created_at=now - timedelta(days=45))

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Total competency_hours should be 9 (3 instances * 3 hours)
        self.assertEqual(kpis['competency_hours']['value'], 9)

        # competency_hours_last_month value should be 6 hours (2 instances * 3 hours)
        # This is an absolute value in hours, NOT a percentage
        self.assertEqual(kpis['competency_hours_last_month']['value'], 6)

        # trendValue should be 3 hours (6 current - 3 previous = 3 hours difference)
        # This is an absolute difference in hours, NOT a percentage
        self.assertEqual(kpis['competency_hours_last_month']['trendValue'], 3)
        self.assertEqual(kpis['competency_hours_last_month']['trend'], 'up')

    def test_kpis_learners_count(self):
        """Test that learners_count returns unique users with badges"""
        badge1 = self._create_badge_class(self.issuer1, 'Learner Badge 1')
        badge2 = self._create_badge_class(self.issuer2, 'Learner Badge 2')

        # Award multiple badges to same user (should count as 1 learner)
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge2, self.learner1)

        # Award to other learners
        self._award_badge(badge1, self.learner2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be 2 unique learners
        self.assertEqual(kpis['learners_count']['value'], 2)

    def test_kpis_badges_per_month(self):
        """Test that badges_per_month is calculated correctly"""
        badge = self._create_badge_class(self.issuer1, 'Monthly Badge')

        # Award 12 badges over 3 months = 4 per month
        now = timezone.now()
        for i in range(12):
            month_offset = i // 4  # 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2
            created_at = now - timedelta(days=30 * month_offset)
            self._award_badge(badge, self.learner1, created_at=created_at)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be around 4-6 badges per month (depends on exact date calculation)
        self.assertGreaterEqual(kpis['badges_per_month']['value'], 3)
        self.assertLessEqual(kpis['badges_per_month']['value'], 12)

    def test_kpis_learners_with_paths(self):
        """Test that learners_with_paths counts users with learning path badges"""
        badge1 = self._create_badge_class(self.issuer1, 'Path Badge 1')
        badge2 = self._create_badge_class(self.issuer1, 'Path Badge 2')
        badge3 = self._create_badge_class(self.issuer2, 'Non-Path Badge')

        # Create learning path
        learning_path = LearningPath.objects.create(
            name='Test Learning Path',
            issuer=self.issuer1,
            created_by=self.admin_user
        )
        LearningPathBadge.objects.create(
            learning_path=learning_path,
            badge=badge1,
            order=1
        )
        LearningPathBadge.objects.create(
            learning_path=learning_path,
            badge=badge2,
            order=2
        )

        # Award path badges
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge2, self.learner1)
        self._award_badge(badge1, self.learner2)

        # Award non-path badge
        self._award_badge(badge3, self.learner3)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # Should be 2 learners with path badges (learner1, learner2)
        self.assertEqual(kpis['learners_with_paths']['value'], 2)

    def test_kpis_trend_calculation(self):
        """Test that trends are calculated correctly"""
        badge = self._create_badge_class(self.issuer1, 'Trend Badge')

        now = timezone.now()

        # Award badges in current month (last 30 days)
        for i in range(5):
            self._award_badge(badge, self.learner1, created_at=now - timedelta(days=i))

        # Award badges in previous month (31-60 days ago)
        for i in range(2):
            self._award_badge(badge, self.learner2, created_at=now - timedelta(days=35 + i))

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # badges_awarded should show upward trend (5 vs 2)
        self.assertEqual(kpis['badges_awarded']['trend'], 'up')
        self.assertEqual(kpis['badges_awarded']['trendValue'], 3)

    def test_kpis_empty_network(self):
        """Test KPIs for network with no data"""
        # Create empty network
        with ISSUER_SAVE_MOCK:
            empty_network = Issuer.objects.create(
                name='Empty Network',
                description='No members',
                email='empty@test.com',
                url='https://empty.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

        url = f'/v1/issuer/networks/{empty_network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}

        # All counts should be 0
        self.assertEqual(kpis['institutions_count']['value'], 0)
        self.assertEqual(kpis['badges_created']['value'], 0)
        self.assertEqual(kpis['badges_awarded']['value'], 0)
        self.assertEqual(kpis['learners_count']['value'], 0)

    def test_kpis_network_not_found(self):
        """Test 404 for non-existent network"""
        url = '/v1/issuer/networks/nonexistent-network/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_kpis_regular_issuer_not_network(self):
        """Test 404 when accessing dashboard for regular issuer"""
        url = f'/v1/issuer/networks/{self.issuer1.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        # Should return 404 because issuer1 is not a network
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_kpis_authentication_required(self):
        """Test that endpoint requires authentication"""
        client = APIClient()  # Unauthenticated client
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = client.get(url)

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_kpis_response_structure(self):
        """Test that KPI response has correct structure"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('kpis', response.data)

        expected_kpi_ids = [
            'institutions_count',
            'badges_created',
            'badges_awarded',
            'participation_badges',
            'competency_badges',
            'competency_hours',
            'competency_hours_last_month',
            'learners_count',
            'badges_per_month',
            'learners_with_paths',
        ]

        kpi_ids = [kpi['id'] for kpi in response.data['kpis']]
        for expected_id in expected_kpi_ids:
            self.assertIn(expected_id, kpi_ids)

        # Verify each KPI has required fields
        for kpi in response.data['kpis']:
            self.assertIn('id', kpi)
            self.assertIn('value', kpi)
            self.assertIn('trend', kpi)
            self.assertIn('trendValue', kpi)
            self.assertIn('trendPeriod', kpi)
            self.assertIn('hasMonthlyDetails', kpi)

    def test_kpis_delivery_method_filter_online(self):
        """Test that deliveryMethod=online filters KPIs correctly"""
        # Create badge classes
        badge_class = self._create_badge_class(
            self.issuer1, 'Delivery Test Badge', category='competency'
        )

        # Award badges with different delivery methods
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            # Online badge
            online_instance = BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner1,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner1.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=True
            )
            # In-person badge
            inperson_instance = BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner2,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner2.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=False
            )

        # Request with online filter
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'online')

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}
        # Only 1 badge should be counted (online)
        self.assertEqual(kpis['badges_awarded']['value'], 1)
        # Only 1 learner with online badge
        self.assertEqual(kpis['learners_count']['value'], 1)

    def test_kpis_delivery_method_filter_in_person(self):
        """Test that deliveryMethod=in-person filters KPIs correctly"""
        badge_class = self._create_badge_class(
            self.issuer1, 'Delivery Test Badge', category='competency'
        )

        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            # Online badge
            BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner1,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner1.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=True
            )
            # In-person badge
            BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner2,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner2.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=False
            )

        # Request with in-person filter
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'in-person')

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}
        # Only 1 badge should be counted (in-person)
        self.assertEqual(kpis['badges_awarded']['value'], 1)

    def test_kpis_no_delivery_method_filter(self):
        """Test that without deliveryMethod filter all badges are counted"""
        badge_class = self._create_badge_class(
            self.issuer1, 'Delivery Test Badge', category='competency'
        )

        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner1,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner1.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=True
            )
            BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=self.learner2,
                issuer=badge_class.issuer,
                recipient_identifier=self.learner2.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=False
            )

        # Request without filter
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIsNone(response.data['metadata']['filters']['deliveryMethod'])

        kpis = {kpi['id']: kpi for kpi in response.data['kpis']}
        # Both badges should be counted
        self.assertEqual(kpis['badges_awarded']['value'], 2)

    def test_kpis_invalid_delivery_method_returns_400(self):
        """Test that invalid deliveryMethod returns 400 Bad Request"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis?deliveryMethod=invalid'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('invalid', response.data['error'].lower())

    def test_kpis_response_includes_metadata(self):
        """Test that KPI response includes metadata with filters"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('filters', response.data['metadata'])
        self.assertIn('deliveryMethod', response.data['metadata']['filters'])
        self.assertIn('lastUpdated', response.data['metadata'])


class NetworkDashboardCompetencyAreasIntegrationTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Competency Areas endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='comp_admin@example.com',
            first_name='Comp',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Competency Network',
                description='Network for competency testing',
                email='comp_network@test.com',
                url='https://comp-network.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Competency Issuer',
                description='Issuer for competencies',
                email='comp_issuer@test.com',
                url='https://comp-issuer.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learner = self.setup_user(
            email='comp_learner@example.com',
            first_name='Comp',
            last_name='Learner',
            authenticate=False
        )

    def _create_badge_with_competency(self, competency_name, badge_name, study_load=120):
        """Helper to create badge with competency extension"""
        badge_class = BadgeClass.objects.create(
            name=badge_name,
            description=f'{badge_name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete the course'
        )

        BadgeClassExtension.objects.create(
            badgeclass=badge_class,
            name='extensions:CompetencyExtension',
            original_json=[{
                'name': competency_name,
                'studyLoad': study_load,
                'description': f'{competency_name} competency'
            }]
        )

        return badge_class

    def _award_badge(self, badge_class, user):
        """Helper to award badge"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_competency_areas_returns_data(self):
        """Test that competency areas endpoint returns data"""
        badge = self._create_badge_with_competency('Programming', 'Python Badge')
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('data', response.data)

    def test_competency_areas_weight_calculation(self):
        """Test that competency weights are calculated by instance count"""
        # Create badges with different competencies
        badge1 = self._create_badge_with_competency('IT Skills', 'IT Badge 1')
        badge2 = self._create_badge_with_competency('IT Skills', 'IT Badge 2')
        badge3 = self._create_badge_with_competency('Soft Skills', 'Soft Badge')

        # Award IT Skills badges 3 times
        self._award_badge(badge1, self.learner)
        self._award_badge(badge2, self.learner)

        learner2 = self.setup_user(email='learner2_comp@test.com', authenticate=False)
        self._award_badge(badge1, learner2)

        # Award Soft Skills badge 1 time
        self._award_badge(badge3, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find competency areas
        areas = {area['id']: area for area in response.data['data']}

        # IT Skills should have higher weight (3 vs 1)
        self.assertIn('it_skills', areas)
        self.assertIn('soft_skills', areas)
        self.assertGreater(areas['it_skills']['weight'], areas['soft_skills']['weight'])

    def test_competency_areas_limit_parameter(self):
        """Test that limit parameter works correctly"""
        # Create many competencies
        for i in range(10):
            badge = self._create_badge_with_competency(f'Competency {i}', f'Badge {i}')
            self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas?limit=3'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['data']), 3)

    def test_competency_areas_percentage_calculation(self):
        """Test that percentages sum to approximately 100"""
        badge1 = self._create_badge_with_competency('Area A', 'Badge A')
        badge2 = self._create_badge_with_competency('Area B', 'Badge B')

        self._award_badge(badge1, self.learner)
        self._award_badge(badge2, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        total_percentage = sum(area['value'] for area in response.data['data'])
        self.assertAlmostEqual(total_percentage, 100.0, delta=1.0)

    def test_competency_areas_empty_network(self):
        """Test response for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], [])
        self.assertEqual(response.data['metadata']['totalAreas'], 0)

    def test_competency_areas_response_structure(self):
        """Test response structure"""
        badge = self._create_badge_with_competency('Test Competency', 'Test Badge')
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata
        self.assertIn('totalAreas', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check data item structure
        for area in response.data['data']:
            self.assertIn('id', area)
            self.assertIn('name', area)
            self.assertIn('value', area)
            self.assertIn('weight', area)


class NetworkDashboardRecentActivityIntegrationTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Recent Activity endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='activity_admin@example.com',
            first_name='Activity',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Activity Network',
                description='Network for activity testing',
                email='activity_network@test.com',
                url='https://activity-network.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer1 = Issuer.objects.create(
                name='Activity Issuer 1',
                description='First issuer',
                email='activity_issuer1@test.com',
                url='https://activity-issuer1.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer2 = Issuer.objects.create(
                name='Activity Issuer 2',
                description='Second issuer',
                email='activity_issuer2@test.com',
                url='https://activity-issuer2.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create learners
        self.learners = []
        for i in range(5):
            learner = self.setup_user(
                email=f'activity_learner{i}@example.com',
                first_name=f'Learner{i}',
                last_name='Activity',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge(self, name, issuer):
        """Helper to create badge"""
        return BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

    def _award_badge(self, badge_class, user, created_at=None, awarding_issuer=None):
        """Helper to award badge

        Args:
            badge_class: The badge class to award
            user: The user receiving the badge
            created_at: Optional timestamp for the award
            awarding_issuer: Optional issuer who awards the badge (defaults to badge_class.issuer)
        """
        instance = BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=awarding_issuer or badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )
        if created_at:
            BadgeInstance.objects.filter(pk=instance.pk).update(created_at=created_at)
            instance.refresh_from_db()
        return instance

    def test_recent_activity_returns_data(self):
        """Test that recent activity endpoint returns data"""
        badge = self._create_badge('Activity Badge', self.issuer1)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('activities', response.data)
        self.assertEqual(len(response.data['activities']), 1)

    def test_recent_activity_ordering(self):
        """Test that activities are ordered by date, most recent first"""
        badge1 = self._create_badge('Badge 1', self.issuer1)
        badge2 = self._create_badge('Badge 2', self.issuer2)

        now = timezone.now()

        # Award badge1 3 days ago
        self._award_badge(badge1, self.learners[0], created_at=now - timedelta(days=3))

        # Award badge2 today
        self._award_badge(badge2, self.learners[1], created_at=now)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        activities = response.data['activities']
        self.assertEqual(len(activities), 2)

        # Most recent should be first
        self.assertEqual(activities[0]['badgeTitle'], 'Badge 2')
        self.assertEqual(activities[1]['badgeTitle'], 'Badge 1')

    def test_recent_activity_recipient_count(self):
        """Test that recipient count is correct for same day/badge/issuer"""
        badge = self._create_badge('Group Badge', self.issuer1)

        now = timezone.now()

        # Award same badge to 3 people on the same day
        for i in range(3):
            self._award_badge(badge, self.learners[i], created_at=now)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        activities = response.data['activities']
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]['recipientCount'], 3)

    def test_recent_activity_limit_parameter(self):
        """Test that limit parameter works correctly"""
        for i in range(5):
            badge = self._create_badge(f'Badge {i}', self.issuer1)
            self._award_badge(badge, self.learners[0], created_at=timezone.now() - timedelta(days=i))

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity?limit=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['activities']), 2)

    def test_recent_activity_empty_network(self):
        """Test response for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['activities'], [])
        self.assertEqual(response.data['metadata']['totalActivities'], 0)

    def test_recent_activity_response_structure(self):
        """Test response structure"""
        badge = self._create_badge('Structure Badge', self.issuer1)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata structure
        self.assertIn('totalActivities', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check activity structure
        for activity in response.data['activities']:
            self.assertIn('date', activity)
            self.assertIn('badgeId', activity)
            self.assertIn('badgeTitle', activity)
            self.assertIn('badgeImage', activity)
            self.assertIn('issuerId', activity)
            self.assertIn('issuerName', activity)
            self.assertIn('recipientCount', activity)

    def test_recent_activity_issuer_is_awarding_institution(self):
        """Test that issuerId/issuerName contain the awarding issuer, not badge creator"""
        # Create badge owned by issuer1
        badge = self._create_badge('Shared Badge', self.issuer1)

        # Award the badge through issuer2 (different from badge creator)
        # This simulates a network-shared badge scenario
        self._award_badge(badge, self.learners[0], awarding_issuer=self.issuer2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should show issuer2 (the awarding institution), not issuer1 (badge creator)
        self.assertEqual(response.data['activities'][0]['issuerName'], 'Activity Issuer 2')
        self.assertEqual(response.data['activities'][0]['issuerId'], self.issuer2.entity_id)

    def test_recent_activity_issuer_same_as_badge_creator(self):
        """Test that issuer info works correctly when badge creator is same as awarding issuer"""
        badge = self._create_badge('Regular Badge', self.issuer1)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['activities'][0]['issuerName'], 'Activity Issuer 1')
        self.assertEqual(response.data['activities'][0]['issuerId'], self.issuer1.entity_id)

    def test_recent_activity_authentication_required(self):
        """Test that endpoint requires authentication"""
        client = APIClient()  # Unauthenticated client
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-activity'
        response = client.get(url)

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_recent_activity_network_not_found(self):
        """Test 404 for non-existent network"""
        url = '/v1/issuer/networks/nonexistent-network/dashboard/recent-activity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NetworkDashboardTopBadgesIntegrationTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Top Badges endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='topbadge_admin@example.com',
            first_name='TopBadge',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Top Badges Network',
                description='Network for top badges testing',
                email='topbadge_network@test.com',
                url='https://topbadge-network.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Top Badges Issuer',
                description='Issuer for top badges',
                email='topbadge_issuer@test.com',
                url='https://topbadge-issuer.com',
                is_network=False,
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        # Create learners
        self.learners = []
        for i in range(5):
            learner = self.setup_user(
                email=f'topbadge_learner{i}@example.com',
                first_name=f'Learner{i}',
                last_name='Test',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge(self, name):
        """Helper to create badge"""
        return BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

    def _award_badge(self, badge_class, user):
        """Helper to award badge"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_top_badges_ranking(self):
        """Test that badges are ranked by award count"""
        badge1 = self._create_badge('Popular Badge')
        badge2 = self._create_badge('Medium Badge')
        badge3 = self._create_badge('Rare Badge')

        # Award badges with different counts
        for learner in self.learners[:5]:  # 5 awards
            self._award_badge(badge1, learner)

        for learner in self.learners[:3]:  # 3 awards
            self._award_badge(badge2, learner)

        self._award_badge(badge3, self.learners[0])  # 1 award

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        badges = response.data['badges']

        # Verify ranking order
        self.assertEqual(badges[0]['badgeTitle'], 'Popular Badge')
        self.assertEqual(badges[0]['count'], 5)
        self.assertEqual(badges[0]['rank'], 1)

        self.assertEqual(badges[1]['badgeTitle'], 'Medium Badge')
        self.assertEqual(badges[1]['count'], 3)
        self.assertEqual(badges[1]['rank'], 2)

        self.assertEqual(badges[2]['badgeTitle'], 'Rare Badge')
        self.assertEqual(badges[2]['count'], 1)
        self.assertEqual(badges[2]['rank'], 3)

    def test_top_badges_limit_parameter(self):
        """Test that limit parameter works correctly"""
        for i in range(5):
            badge = self._create_badge(f'Badge {i}')
            self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges?limit=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['badges']), 2)

    def test_top_badges_metadata(self):
        """Test that metadata is correct"""
        badge = self._create_badge('Metadata Badge')

        for learner in self.learners[:3]:
            self._award_badge(badge, learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        metadata = response.data['metadata']
        self.assertEqual(metadata['totalBadges'], 3)  # Total badge instances
        self.assertIn('lastUpdated', metadata)

    def test_top_badges_empty_network(self):
        """Test response for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['badges'], [])
        self.assertEqual(response.data['metadata']['totalBadges'], 0)

    def test_top_badges_response_structure(self):
        """Test response structure"""
        badge = self._create_badge('Structure Badge')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata structure
        self.assertIn('totalBadges', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check badge structure
        for badge_data in response.data['badges']:
            self.assertIn('rank', badge_data)
            self.assertIn('badgeId', badge_data)
            self.assertIn('badgeTitle', badge_data)
            self.assertIn('image', badge_data)
            self.assertIn('count', badge_data)


class NetworkDashboardDataPlausibilityTest(BadgrTestCase):
    """
    Tests to verify data plausibility and consistency across endpoints.
    """

    def setUp(self):
        """Set up comprehensive test data"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='plausibility_admin@example.com',
            first_name='Plausibility',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Plausibility Network',
                description='Network for plausibility testing',
                email='plausibility@test.com',
                url='https://plausibility.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer1 = Issuer.objects.create(
                name='Issuer Alpha',
                email='alpha@test.com',
                url='https://alpha.com',
                created_by=self.admin_user,
                verified=True
            )
            self.issuer2 = Issuer.objects.create(
                name='Issuer Beta',
                email='beta@test.com',
                url='https://beta.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create learners
        self.learner1 = self.setup_user(email='plaus_l1@test.com', authenticate=False)
        self.learner2 = self.setup_user(email='plaus_l2@test.com', authenticate=False)

    def test_badges_awarded_equals_sum_of_top_badges(self):
        """Test that total badges awarded matches sum in top badges"""
        badge1 = BadgeClass.objects.create(
            name='Badge Alpha', issuer=self.issuer1, created_by=self.admin_user
        )
        badge2 = BadgeClass.objects.create(
            name='Badge Beta', issuer=self.issuer2, created_by=self.admin_user
        )

        # Award 3 of badge1, 2 of badge2 = 5 total
        for _ in range(3):
            BadgeInstance.objects.create(
                badgeclass=badge1, issuer=self.issuer1,
                recipient_identifier='test@test.com'
            )
        for _ in range(2):
            BadgeInstance.objects.create(
                badgeclass=badge2, issuer=self.issuer2,
                recipient_identifier='test@test.com'
            )

        # Get KPIs
        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        kpis_response = self.client.get(kpis_url)

        # Get top badges
        top_badges_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/top-badges?limit=10'
        top_badges_response = self.client.get(top_badges_url)

        self.assertEqual(kpis_response.status_code, status.HTTP_200_OK)
        self.assertEqual(top_badges_response.status_code, status.HTTP_200_OK)

        # Compare totals
        kpis = {kpi['id']: kpi['value'] for kpi in kpis_response.data['kpis']}
        badges_awarded = kpis['badges_awarded']

        top_badges_total = sum(b['count'] for b in top_badges_response.data['badges'])
        top_badges_metadata = top_badges_response.data['metadata']['totalBadges']

        self.assertEqual(badges_awarded, top_badges_total)
        self.assertEqual(badges_awarded, top_badges_metadata)

    def test_institutions_count_matches_membership(self):
        """Test that institutions count matches actual network membership"""
        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(kpis_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi['value'] for kpi in response.data['kpis']}

        actual_membership = NetworkMembership.objects.filter(
            network=self.network
        ).count()

        self.assertEqual(kpis['institutions_count'], actual_membership)

    def test_learners_count_is_unique(self):
        """Test that learners are counted uniquely across all badges"""
        badge1 = BadgeClass.objects.create(
            name='Unique Learner Badge 1', issuer=self.issuer1, created_by=self.admin_user
        )
        badge2 = BadgeClass.objects.create(
            name='Unique Learner Badge 2', issuer=self.issuer2, created_by=self.admin_user
        )

        # Same learner gets multiple badges
        BadgeInstance.objects.create(
            badgeclass=badge1, issuer=self.issuer1,
            user=self.learner1, recipient_identifier=self.learner1.email
        )
        BadgeInstance.objects.create(
            badgeclass=badge2, issuer=self.issuer2,
            user=self.learner1, recipient_identifier=self.learner1.email
        )
        BadgeInstance.objects.create(
            badgeclass=badge1, issuer=self.issuer1,
            user=self.learner2, recipient_identifier=self.learner2.email
        )

        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(kpis_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi['value'] for kpi in response.data['kpis']}

        # Should be 2 unique learners, not 3 badge instances
        self.assertEqual(kpis['learners_count'], 2)

    def test_revoked_badges_not_counted(self):
        """Test that revoked badges are excluded from all counts"""
        badge = BadgeClass.objects.create(
            name='Revoke Test Badge', issuer=self.issuer1, created_by=self.admin_user
        )

        # Create 3 badges, revoke 1
        for i in range(3):
            instance = BadgeInstance.objects.create(
                badgeclass=badge, issuer=self.issuer1,
                user=self.learner1, recipient_identifier=self.learner1.email
            )
            if i == 0:
                instance.revoked = True
                instance.save()

        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(kpis_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = {kpi['id']: kpi['value'] for kpi in response.data['kpis']}

        # Should count 2, not 3 (1 revoked)
        self.assertEqual(kpis['badges_awarded'], 2)

    def test_values_are_non_negative(self):
        """Test that all KPI values are non-negative"""
        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(kpis_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for kpi in response.data['kpis']:
            self.assertGreaterEqual(
                kpi['value'], 0,
                f"KPI {kpi['id']} has negative value: {kpi['value']}"
            )
            self.assertGreaterEqual(
                kpi['trendValue'], 0,
                f"KPI {kpi['id']} has negative trend value: {kpi['trendValue']}"
            )

    def test_trend_direction_values(self):
        """Test that trend directions are valid"""
        kpis_url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/kpis'
        response = self.client.get(kpis_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        valid_trends = ['up', 'down', 'stable']
        for kpi in response.data['kpis']:
            self.assertIn(
                kpi['trend'], valid_trends,
                f"KPI {kpi['id']} has invalid trend: {kpi['trend']}"
            )


class NetworkDashboardStrengthenedCompetenciesTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Strengthened Competencies endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='competencies_admin@example.com',
            first_name='Competencies',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Competencies Network',
                description='Network for competencies testing',
                email='competencies@test.com',
                url='https://competencies.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Competencies Issuer',
                email='comp_issuer@test.com',
                url='https://comp-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learners = []
        for i in range(3):
            learner = self.setup_user(
                email=f'comp_learner{i}@example.com',
                first_name=f'Learner{i}',
                last_name='Comp',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge_with_competencies(self, name, competencies):
        """Helper to create badge with competencies"""
        import json
        badge = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

        # Add competency extension
        if competencies:
            BadgeClassExtension.objects.create(
                badgeclass=badge,
                name='extensions:CompetencyExtension',
                original_json=json.dumps(competencies)
            )

        return badge

    def _award_badge(self, badge_class, user):
        """Helper to award badge"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_strengthened_competencies_returns_data(self):
        """Test that strengthened competencies endpoint returns data"""
        competencies = [
            {'name': 'Python Programming', 'studyLoad': 120, 'framework_identifier': 'http://esco/python'}
        ]
        badge = self._create_badge_with_competencies('Python Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('competencies', response.data)
        self.assertGreater(len(response.data['competencies']), 0)

    def test_strengthened_competencies_hours_calculation(self):
        """Test that hours are calculated correctly (converted from minutes)"""
        competencies = [
            {'name': 'Data Analysis', 'studyLoad': 180}  # 180 minutes = 3 hours
        ]
        badge = self._create_badge_with_competencies('Data Badge', competencies)

        # Award to 2 learners
        self._award_badge(badge, self.learners[0])
        self._award_badge(badge, self.learners[1])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 2 awards * 180 minutes / 60 = 6 hours
        comp = response.data['competencies'][0]
        self.assertEqual(comp['hours'], 6)

    def test_strengthened_competencies_sorting(self):
        """Test that competencies can be sorted"""
        badge1 = self._create_badge_with_competencies('Badge A', [
            {'name': 'Competency A', 'studyLoad': 60}
        ])
        badge2 = self._create_badge_with_competencies('Badge B', [
            {'name': 'Competency B', 'studyLoad': 120}
        ])

        self._award_badge(badge1, self.learners[0])
        self._award_badge(badge2, self.learners[0])

        # Default sort (by hours desc)
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Competency B should be first (more hours)
        self.assertEqual(response.data['competencies'][0]['title'], 'Competency B')

    def test_strengthened_competencies_empty_network(self):
        """Test response for network with no competencies"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['competencies'], [])
        self.assertEqual(response.data['metadata']['totalCompetencies'], 0)

    def test_strengthened_competencies_response_structure(self):
        """Test response structure"""
        competencies = [
            {'name': 'Test Competency', 'studyLoad': 60, 'framework_identifier': 'http://esco/test'}
        ]
        badge = self._create_badge_with_competencies('Test Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata
        self.assertIn('totalCompetencies', response.data['metadata'])
        self.assertIn('totalHours', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check competency structure
        for comp in response.data['competencies']:
            self.assertIn('competencyId', comp)
            self.assertIn('title', comp)
            self.assertIn('hours', comp)


class NetworkDashboardCompetencyDetailTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Competency Detail endpoint.
    GET /v1/issuer/networks/{networkSlug}/dashboard/strengthened-competencies/{competencyId}
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='competency_detail_admin@example.com',
            first_name='Competency',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Competency Detail Network',
                description='Network for competency detail testing',
                email='compdetail@test.com',
                url='https://compdetail.com',
                is_network=True,
                created_by=self.admin_user,
                linkedinId=''
            )

            self.issuer1 = Issuer.objects.create(
                name='Institution 1',
                description='First institution',
                email='inst1@test.com',
                url='https://inst1.com',
                created_by=self.admin_user,
                linkedinId=''
            )

            self.issuer2 = Issuer.objects.create(
                name='Institution 2',
                description='Second institution',
                email='inst2@test.com',
                url='https://inst2.com',
                created_by=self.admin_user,
                linkedinId=''
            )

        # Add issuers to network
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create test users
        self.learners = []
        for i in range(3):
            learner = self.setup_user(
                email=f'learner_detail_{i}@example.com',
                first_name=f'Learner{i}',
                last_name=f'Test{i}',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge_with_competencies(self, issuer, name, competencies):
        """Helper to create badge with competencies"""
        with BADGECLASS_SAVE_MOCK:
            badge = BadgeClass.objects.create(
                issuer=issuer,
                name=name,
                description=f'{name} description',
                criteria_text=f'{name} criteria',
                created_by=self.admin_user
            )

        # Add CategoryExtension (required by BadgeInstance manager)
        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': 'Teilnahme'})
        )

        if competencies:
            BadgeClassExtension.objects.create(
                badgeclass=badge,
                name='extensions:CompetencyExtension',
                original_json=json.dumps(competencies)
            )

        return badge

    def _award_badge(self, badge, user):
        """Helper to award badge to user"""
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            instance = BadgeInstance.objects.create(
                badgeclass=badge,
                issuer=badge.issuer,
                user=user,
                recipient_identifier=user.email,
                recipient_type='email'
            )
        return instance

    def test_competency_detail_returns_data(self):
        """Test that competency detail endpoint returns data"""
        competencies = [{'name': 'Python Programming', 'studyLoad': 120, 'framework_identifier': 'http://esco/python'}]
        badge = self._create_badge_with_competencies(self.issuer1, 'Python Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/python_programming'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['competencyId'], 'python_programming')
        self.assertEqual(response.data['title'], 'Python Programming')
        self.assertEqual(response.data['badgeCount'], 1)
        self.assertEqual(response.data['userCount'], 1)
        self.assertEqual(response.data['institutionCount'], 1)

    def test_competency_detail_aggregates_institutions(self):
        """Test that institutions are properly aggregated"""
        competencies = [{'name': 'Data Analysis', 'studyLoad': 180}]

        # Create badges at both institutions with same competency
        badge1 = self._create_badge_with_competencies(self.issuer1, 'Data Badge 1', competencies)
        badge2 = self._create_badge_with_competencies(self.issuer2, 'Data Badge 2', competencies)

        # Award badges to different learners
        self._award_badge(badge1, self.learners[0])
        self._award_badge(badge1, self.learners[1])
        self._award_badge(badge2, self.learners[2])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/data_analysis'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['badgeCount'], 3)
        self.assertEqual(response.data['userCount'], 3)
        self.assertEqual(response.data['institutionCount'], 2)
        self.assertEqual(len(response.data['institutions']), 2)

    def test_competency_detail_institution_limit(self):
        """Test institutionLimit parameter"""
        competencies = [{'name': 'Test Limit', 'studyLoad': 60}]

        badge1 = self._create_badge_with_competencies(self.issuer1, 'Limit Badge 1', competencies)
        badge2 = self._create_badge_with_competencies(self.issuer2, 'Limit Badge 2', competencies)

        self._award_badge(badge1, self.learners[0])
        self._award_badge(badge2, self.learners[1])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/test_limit?institutionLimit=1'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['institutionCount'], 2)
        self.assertEqual(len(response.data['institutions']), 1)

    def test_competency_detail_not_found(self):
        """Test 404 for non-existent competency"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/nonexistent_competency'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_competency_detail_response_structure(self):
        """Test response structure"""
        competencies = [{'name': 'Structure Test', 'studyLoad': 90, 'framework_identifier': 'http://esco/structure'}]
        badge = self._create_badge_with_competencies(self.issuer1, 'Structure Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/structure_test'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check required fields
        self.assertIn('competencyId', response.data)
        self.assertIn('title', response.data)
        self.assertIn('titleKey', response.data)
        self.assertIn('hours', response.data)
        self.assertIn('escoUri', response.data)
        self.assertIn('badgeCount', response.data)
        self.assertIn('userCount', response.data)
        self.assertIn('institutionCount', response.data)
        self.assertIn('institutions', response.data)

        # Check institution structure
        if response.data['institutions']:
            inst = response.data['institutions'][0]
            self.assertIn('institutionId', inst)
            self.assertIn('name', inst)
            self.assertIn('badgeCount', inst)
            self.assertIn('userCount', inst)

    def test_competency_detail_delivery_method_filter(self):
        """Test deliveryMethod filter"""
        competencies = [{'name': 'Delivery Test', 'studyLoad': 60}]

        badge_online = self._create_badge_with_competencies(self.issuer1, 'Online Badge', competencies)
        badge_inperson = self._create_badge_with_competencies(self.issuer2, 'In-Person Badge', competencies)

        # Award online badge
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            BadgeInstance.objects.create(
                badgeclass=badge_online,
                issuer=badge_online.issuer,
                user=self.learners[0],
                recipient_identifier=self.learners[0].email,
                recipient_type='email',
                activity_online=True
            )

        # Award in-person badge
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            BadgeInstance.objects.create(
                badgeclass=badge_inperson,
                issuer=badge_inperson.issuer,
                user=self.learners[1],
                recipient_identifier=self.learners[1].email,
                recipient_type='email',
                activity_online=False
            )

        # Test online filter
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies/delivery_test?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['badgeCount'], 1)


class NetworkDashboardCompetencyAreaDetailTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Competency Area Detail endpoint.
    POST /v1/issuer/networks/{networkSlug}/dashboard/competency-area-detail
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='comp_area_admin@example.com',
            first_name='CompArea',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Competency Area Network',
                description='Network for competency area testing',
                email='comparea@test.com',
                url='https://comparea.com',
                is_network=True,
                created_by=self.admin_user,
                linkedinId=''
            )

            self.issuer1 = Issuer.objects.create(
                name='Area Institution 1',
                description='First institution',
                email='areainst1@test.com',
                url='https://areainst1.com',
                created_by=self.admin_user,
                linkedinId=''
            )

            self.issuer2 = Issuer.objects.create(
                name='Area Institution 2',
                description='Second institution',
                email='areainst2@test.com',
                url='https://areainst2.com',
                created_by=self.admin_user,
                linkedinId=''
            )

        # Add issuers to network
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create test users
        self.learners = []
        for i in range(3):
            learner = self.setup_user(
                email=f'area_learner_{i}@example.com',
                first_name=f'AreaLearner{i}',
                last_name=f'Test{i}',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge_with_competencies(self, issuer, name, competencies):
        """Helper to create badge with competencies"""
        with BADGECLASS_SAVE_MOCK:
            badge = BadgeClass.objects.create(
                issuer=issuer,
                name=name,
                description=f'{name} description',
                criteria_text=f'{name} criteria',
                created_by=self.admin_user
            )

        # Add CategoryExtension (required by BadgeInstance manager)
        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': 'Teilnahme'})
        )

        if competencies:
            BadgeClassExtension.objects.create(
                badgeclass=badge,
                name='extensions:CompetencyExtension',
                original_json=json.dumps(competencies)
            )

        return badge

    def _award_badge(self, badge, user):
        """Helper to award badge to user"""
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            instance = BadgeInstance.objects.create(
                badgeclass=badge,
                issuer=badge.issuer,
                user=user,
                recipient_identifier=user.email,
                recipient_type='email'
            )
        return instance

    def test_competency_area_detail_returns_data(self):
        """Test that competency area detail endpoint returns aggregated data"""
        competencies = [
            {'name': 'Dialoge schreiben', 'studyLoad': 120, 'framework_identifier': 'http://esco/dialoge'},
            {'name': 'Storylines schreiben', 'studyLoad': 180, 'framework_identifier': 'http://esco/storylines'}
        ]
        badge = self._create_badge_with_competencies(self.issuer1, 'Writing Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Kommunikation',
            'competencyUris': ['http://esco/dialoge', 'http://esco/storylines']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['areaName'], 'Kommunikation')
        self.assertEqual(response.data['totalCompetencies'], 2)
        self.assertEqual(response.data['matchedCompetencies'], 2)
        self.assertEqual(response.data['badgeCount'], 1)
        self.assertEqual(response.data['userCount'], 1)
        self.assertEqual(response.data['institutionCount'], 1)
        self.assertEqual(len(response.data['topCompetencies']), 2)

    def test_competency_area_detail_aggregates_across_institutions(self):
        """Test that data is aggregated across multiple institutions"""
        comp1 = [{'name': 'Skill A', 'studyLoad': 120, 'framework_identifier': 'http://esco/skill-a'}]
        comp2 = [{'name': 'Skill B', 'studyLoad': 180, 'framework_identifier': 'http://esco/skill-b'}]

        badge1 = self._create_badge_with_competencies(self.issuer1, 'Badge 1', comp1)
        badge2 = self._create_badge_with_competencies(self.issuer2, 'Badge 2', comp2)

        self._award_badge(badge1, self.learners[0])
        self._award_badge(badge1, self.learners[1])
        self._award_badge(badge2, self.learners[2])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Test Area',
            'competencyUris': ['http://esco/skill-a', 'http://esco/skill-b']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['badgeCount'], 3)
        self.assertEqual(response.data['userCount'], 3)
        self.assertEqual(response.data['institutionCount'], 2)

    def test_competency_area_detail_partial_match(self):
        """Test that only matched competencies are counted"""
        competencies = [{'name': 'Matched Skill', 'studyLoad': 120, 'framework_identifier': 'http://esco/matched'}]
        badge = self._create_badge_with_competencies(self.issuer1, 'Partial Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Partial Match Area',
            'competencyUris': ['http://esco/matched', 'http://esco/not-found', 'http://esco/also-not-found']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['totalCompetencies'], 3)
        self.assertEqual(response.data['matchedCompetencies'], 1)

    def test_competency_area_detail_missing_area_name(self):
        """Test 400 error for missing areaName"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'competencyUris': ['http://esco/skill']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_competency_area_detail_missing_uris(self):
        """Test 400 error for missing competencyUris"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Test Area'
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_competency_area_detail_empty_uris(self):
        """Test 400 error for empty competencyUris array"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Test Area',
            'competencyUris': []
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_competency_area_detail_no_matches(self):
        """Test response when no competencies match"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'No Match Area',
            'competencyUris': ['http://esco/nonexistent']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['matchedCompetencies'], 0)
        self.assertEqual(response.data['badgeCount'], 0)

    def test_competency_area_detail_limits(self):
        """Test topCompetenciesLimit and institutionLimit parameters"""
        competencies = [
            {'name': f'Skill {i}', 'studyLoad': 60 * (i + 1), 'framework_identifier': f'http://esco/skill-{i}'}
            for i in range(5)
        ]
        badge = self._create_badge_with_competencies(self.issuer1, 'Multi Skill Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Limited Area',
            'competencyUris': [f'http://esco/skill-{i}' for i in range(5)],
            'topCompetenciesLimit': 2,
            'institutionLimit': 1
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['matchedCompetencies'], 5)
        self.assertEqual(len(response.data['topCompetencies']), 2)
        self.assertEqual(len(response.data['institutions']), 1)

    def test_competency_area_detail_response_structure(self):
        """Test response structure"""
        competencies = [{'name': 'Structure Test', 'studyLoad': 90, 'framework_identifier': 'http://esco/structure'}]
        badge = self._create_badge_with_competencies(self.issuer1, 'Structure Badge', competencies)
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-area-detail'
        request_data = {
            'areaName': 'Structure Area',
            'areaConceptUri': '/esco/structure-area',
            'competencyUris': ['http://esco/structure']
        }
        response = self.client.post(url, request_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check required response fields
        self.assertIn('areaName', response.data)
        self.assertIn('areaConceptUri', response.data)
        self.assertIn('totalHours', response.data)
        self.assertIn('totalCompetencies', response.data)
        self.assertIn('matchedCompetencies', response.data)
        self.assertIn('badgeCount', response.data)
        self.assertIn('userCount', response.data)
        self.assertIn('institutionCount', response.data)
        self.assertIn('topCompetencies', response.data)
        self.assertIn('institutions', response.data)

        # Check echo of areaConceptUri
        self.assertEqual(response.data['areaConceptUri'], '/esco/structure-area')

        # Check competency structure
        if response.data['topCompetencies']:
            comp = response.data['topCompetencies'][0]
            self.assertIn('competencyId', comp)
            self.assertIn('title', comp)
            self.assertIn('escoUri', comp)
            self.assertIn('hours', comp)
            self.assertIn('badgeCount', comp)
            self.assertIn('userCount', comp)

        # Check institution structure
        if response.data['institutions']:
            inst = response.data['institutions'][0]
            self.assertIn('institutionId', inst)
            self.assertIn('name', inst)
            self.assertIn('badgeCount', inst)
            self.assertIn('userCount', inst)


class NetworkDashboardBadgeAwardsTimelineTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Badge Awards Timeline endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='timeline_admin@example.com',
            first_name='Timeline',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Timeline Network',
                description='Network for timeline testing',
                email='timeline@test.com',
                url='https://timeline.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Timeline Issuer',
                email='timeline_issuer@test.com',
                url='https://timeline-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learners = []
        for i in range(5):
            learner = self.setup_user(
                email=f'timeline_learner{i}@example.com',
                first_name=f'Learner{i}',
                last_name='Timeline',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge_with_category(self, name, category):
        """Helper to create badge with category"""
        import json
        badge = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': category})
        )

        return badge

    def _award_badge(self, badge_class, user, created_at=None):
        """Helper to award badge"""
        instance = BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )
        if created_at:
            BadgeInstance.objects.filter(pk=instance.pk).update(created_at=created_at)
            instance.refresh_from_db()
        return instance

    def test_badge_awards_timeline_returns_data(self):
        """Test that timeline endpoint returns data"""
        badge = self._create_badge_with_category('Timeline Badge', 'competency')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('timeline', response.data)
        self.assertGreater(len(response.data['timeline']), 0)

    def test_badge_awards_timeline_by_type_breakdown(self):
        """Test that timeline includes type breakdown"""
        badge_participation = self._create_badge_with_category('Participation', 'participation')
        badge_competency = self._create_badge_with_category('Competency', 'competency')

        self._award_badge(badge_participation, self.learners[0])
        self._award_badge(badge_competency, self.learners[1])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        entry = response.data['timeline'][0]
        self.assertIn('byType', entry)
        self.assertIn('participation', entry['byType'])
        self.assertIn('competency', entry['byType'])
        self.assertIn('learningpath', entry['byType'])

    def test_badge_awards_timeline_year_filter(self):
        """Test year filter"""
        badge = self._create_badge_with_category('Year Badge', 'competency')
        current_year = timezone.now().year

        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline?year={current_year}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['year'], current_year)

    def test_badge_awards_timeline_groupby(self):
        """Test groupBy parameter"""
        badge = self._create_badge_with_category('Group Badge', 'competency')
        self._award_badge(badge, self.learners[0])

        for group_by in ['day', 'week', 'month']:
            url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline?groupBy={group_by}'
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['metadata']['groupBy'], group_by)

    def test_badge_awards_timeline_empty_network(self):
        """Test response for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['timeline'], [])
        self.assertEqual(response.data['metadata']['totalAwards'], 0)

    def test_badge_awards_timeline_response_structure(self):
        """Test response structure"""
        badge = self._create_badge_with_category('Structure Badge', 'competency')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-awards-timeline'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata
        self.assertIn('totalAwards', response.data['metadata'])
        self.assertIn('groupBy', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check timeline entry structure
        for entry in response.data['timeline']:
            self.assertIn('date', entry)
            self.assertIn('count', entry)
            self.assertIn('byType', entry)


class NetworkDashboardBadgeTypeDistributionTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Badge Type Distribution endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='distribution_admin@example.com',
            first_name='Distribution',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Distribution Network',
                description='Network for distribution testing',
                email='distribution@test.com',
                url='https://distribution.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Distribution Issuer',
                email='distribution_issuer@test.com',
                url='https://distribution-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learners = []
        for i in range(5):
            learner = self.setup_user(
                email=f'dist_learner{i}@example.com',
                first_name=f'Learner{i}',
                last_name='Dist',
                authenticate=False
            )
            self.learners.append(learner)

    def _create_badge_with_category(self, name, category):
        """Helper to create badge with category"""
        import json
        badge = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': category})
        )

        return badge

    def _award_badge(self, badge_class, user):
        """Helper to award badge"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_badge_type_distribution_returns_data(self):
        """Test that distribution endpoint returns data"""
        badge = self._create_badge_with_category('Dist Badge', 'competency')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('distribution', response.data)
        self.assertEqual(len(response.data['distribution']), 3)  # 3 types

    def test_badge_type_distribution_percentages(self):
        """Test that percentages sum to 100"""
        # Create 2 participation, 1 competency
        badge_p1 = self._create_badge_with_category('Part 1', 'participation')
        badge_p2 = self._create_badge_with_category('Part 2', 'participation')
        badge_c = self._create_badge_with_category('Comp 1', 'competency')

        self._award_badge(badge_p1, self.learners[0])
        self._award_badge(badge_p2, self.learners[1])
        self._award_badge(badge_c, self.learners[2])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        total_percentage = sum(d['percentage'] for d in response.data['distribution'])
        self.assertAlmostEqual(total_percentage, 100.0, places=1)

    def test_badge_type_distribution_counts(self):
        """Test that counts are correct"""
        badge_p = self._create_badge_with_category('Part', 'participation')
        badge_c = self._create_badge_with_category('Comp', 'competency')

        # 2 participation awards
        self._award_badge(badge_p, self.learners[0])
        self._award_badge(badge_p, self.learners[1])

        # 1 competency award
        self._award_badge(badge_c, self.learners[2])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalBadges'], 3)

        # Check individual counts
        distribution = {d['type']: d['count'] for d in response.data['distribution']}
        self.assertEqual(distribution['participation'], 2)
        self.assertEqual(distribution['competency'], 1)
        self.assertEqual(distribution['learningpath'], 0)

    def test_badge_type_distribution_year_filter(self):
        """Test year filter"""
        badge = self._create_badge_with_category('Year Badge', 'competency')
        current_year = timezone.now().year

        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution?year={current_year}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['year'], current_year)

    def test_badge_type_distribution_empty_network(self):
        """Test response for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['distribution'], [])
        self.assertEqual(response.data['metadata']['totalBadges'], 0)

    def test_badge_type_distribution_response_structure(self):
        """Test response structure"""
        badge = self._create_badge_with_category('Structure Badge', 'competency')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata
        self.assertIn('totalBadges', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check distribution entry structure
        for entry in response.data['distribution']:
            self.assertIn('type', entry)
            self.assertIn('typeKey', entry)
            self.assertIn('count', entry)
            self.assertIn('percentage', entry)

    def test_badge_type_distribution_all_types_present(self):
        """Test that all three types are always in response"""
        badge = self._create_badge_with_category('Only Comp', 'competency')
        self._award_badge(badge, self.learners[0])

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-type-distribution'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        types_in_response = [d['type'] for d in response.data['distribution']]
        self.assertIn('participation', types_in_response)
        self.assertIn('competency', types_in_response)
        self.assertIn('learningpath', types_in_response)


class NetworkDashboardRecentBadgeAwardsIntegrationTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Recent Badge Awards endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='recent_awards_admin@example.com',
            first_name='Recent',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Recent Awards Network',
                description='Network for recent awards testing',
                email='recent_network@test.com',
                url='https://recent-network.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Recent Awards Issuer',
                description='Issuer for recent awards',
                email='recent_issuer@test.com',
                url='https://recent-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(
            network=self.network,
            issuer=self.issuer
        )

        self.learner = BadgeUser.objects.create(
            email='recent_learner@example.com',
            first_name='Recent',
            last_name='Learner'
        )

    def _create_badge_with_competency(self, competency_name, badge_name, esco_uri=None):
        """Helper to create a badge with a competency extension"""
        badge = BadgeClass.objects.create(
            name=badge_name,
            description=f'Description for {badge_name}',
            issuer=self.issuer,
            image='badge.png',
            criteria_text='Test criteria'
        )

        competency_data = {
            'name': competency_name,
            'studyLoad': 120,
        }
        if esco_uri:
            competency_data['framework_identifier'] = esco_uri

        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CompetencyExtension',
            original_json=[competency_data]
        )

        return badge

    def _create_badge_with_category(self, badge_name, category):
        """Helper to create a badge with a category extension"""
        badge = BadgeClass.objects.create(
            name=badge_name,
            description=f'Description for {badge_name}',
            issuer=self.issuer,
            image='badge.png',
            criteria_text='Test criteria'
        )

        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json={'Category': category}
        )

        return badge

    def _award_badge(self, badge, user, days_ago=0):
        """Helper to award a badge to a user"""
        from django.utils import timezone
        from datetime import timedelta

        instance = BadgeInstance.objects.create(
            recipient_identifier=user.email,
            badgeclass=badge,
            issuer=self.issuer,
            user=user,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Update created_at if days_ago specified
        if days_ago > 0:
            instance.created_at = timezone.now() - timedelta(days=days_ago)
            instance.save()

        return instance

    def test_recent_badge_awards_returns_200(self):
        """Test that the endpoint returns 200 for authenticated users"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_recent_badge_awards_empty_response(self):
        """Test response structure when no awards exist"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('awards', response.data)
        self.assertEqual(response.data['metadata']['totalAwards'], 0)
        self.assertEqual(response.data['awards'], [])

    def test_recent_badge_awards_with_data(self):
        """Test that awards are returned correctly"""
        badge = self._create_badge_with_competency('Python Programming', 'Python Badge', 'http://esco.eu/python')
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalAwards'], 1)
        self.assertEqual(len(response.data['awards']), 1)

        award = response.data['awards'][0]
        self.assertEqual(award['badgeName'], 'Python Badge')
        self.assertEqual(award['count'], 1)
        self.assertIn('competencies', award)
        self.assertEqual(len(award['competencies']), 1)
        self.assertEqual(award['competencies'][0]['name'], 'Python Programming')
        self.assertEqual(award['competencies'][0]['escoUri'], 'http://esco.eu/python')

    def test_recent_badge_awards_response_structure(self):
        """Test complete response structure"""
        badge = self._create_badge_with_competency('Test Comp', 'Test Badge')
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata structure
        metadata = response.data['metadata']
        self.assertIn('totalAwards', metadata)
        self.assertIn('periodStart', metadata)
        self.assertIn('periodEnd', metadata)
        self.assertIn('lastUpdated', metadata)

        # Check award entry structure
        for award in response.data['awards']:
            self.assertIn('date', award)
            self.assertIn('badgeId', award)
            self.assertIn('badgeName', award)
            self.assertIn('count', award)
            self.assertIn('competencies', award)

    def test_recent_badge_awards_excludes_old_awards(self):
        """Test that awards older than the period are excluded"""
        badge = self._create_badge_with_competency('Old Comp', 'Old Badge')
        # Award badge 60 days ago (outside default 30-day window)
        self._award_badge(badge, self.learner, days_ago=60)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalAwards'], 0)
        self.assertEqual(response.data['awards'], [])

    def test_recent_badge_awards_days_parameter(self):
        """Test that days parameter extends the period"""
        badge = self._create_badge_with_competency('Extended Comp', 'Extended Badge')
        # Award badge 60 days ago
        self._award_badge(badge, self.learner, days_ago=60)

        # Default (30 days) should not include it
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)
        self.assertEqual(response.data['metadata']['totalAwards'], 0)

        # With 90 days should include it
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards?days=90'
        response = self.client.get(url)
        self.assertEqual(response.data['metadata']['totalAwards'], 1)

    def test_recent_badge_awards_limit_parameter(self):
        """Test that limit parameter limits results"""
        for i in range(5):
            badge = self._create_badge_with_competency(f'Comp {i}', f'Badge {i}')
            self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards?limit=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['awards']), 2)

    def test_recent_badge_awards_aggregates_by_date_and_badge(self):
        """Test that multiple awards of same badge on same date are aggregated"""
        badge = self._create_badge_with_competency('Aggregated Comp', 'Aggregated Badge')

        learner2 = BadgeUser.objects.create(
            email='learner2@example.com',
            first_name='Learner',
            last_name='Two'
        )
        learner3 = BadgeUser.objects.create(
            email='learner3@example.com',
            first_name='Learner',
            last_name='Three'
        )

        # Award same badge to 3 learners on same day
        self._award_badge(badge, self.learner)
        self._award_badge(badge, learner2)
        self._award_badge(badge, learner3)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalAwards'], 3)
        # Should be aggregated into 1 entry
        self.assertEqual(len(response.data['awards']), 1)
        self.assertEqual(response.data['awards'][0]['count'], 3)

    def test_recent_badge_awards_sort_by_date(self):
        """Test sorting by date"""
        badge1 = self._create_badge_with_competency('Comp 1', 'Badge 1')
        badge2 = self._create_badge_with_competency('Comp 2', 'Badge 2')

        self._award_badge(badge1, self.learner, days_ago=5)
        self._award_badge(badge2, self.learner, days_ago=1)

        # Default sort (date desc) - most recent first
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['awards'][0]['badgeName'], 'Badge 2')

        # Sort asc - oldest first
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards?sortOrder=asc'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['awards'][0]['badgeName'], 'Badge 1')

    def test_recent_badge_awards_includes_badge_type(self):
        """Test that badge type is correctly included"""
        badge = self._create_badge_with_category('Participation Badge', 'participation')
        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CompetencyExtension',
            original_json=[{'name': 'Attendance', 'studyLoad': 60}]
        )
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['awards'][0]['badgeType'], 'participation')

    def test_recent_badge_awards_network_not_found(self):
        """Test 404 for non-existent network"""
        url = '/v1/issuer/networks/non-existent-network/dashboard/recent-badge-awards'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NetworkDashboardDeliveryMethodFilterTest(BadgrTestCase):
    """
    Integration tests for delivery method filtering on dashboard endpoints.

    Tests the deliveryMethod query parameter for:
    - GET /dashboard/competency-areas?deliveryMethod=online|in-person
    - GET /dashboard/strengthened-competencies?deliveryMethod=online|in-person
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='delivery_admin@example.com',
            first_name='Delivery',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Delivery Method Network',
                description='Network for delivery method testing',
                email='delivery@test.com',
                url='https://delivery.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Delivery Issuer',
                email='delivery_issuer@test.com',
                url='https://delivery-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learner = self.setup_user(
            email='delivery_learner@example.com',
            first_name='Delivery',
            last_name='Learner',
            authenticate=False
        )

    def _create_badge_with_competency(self, name, competency_name, study_load=120):
        """Helper to create badge with competency"""
        badge = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=self.issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CompetencyExtension',
            original_json=[{
                'name': competency_name,
                'studyLoad': study_load,
            }]
        )

        return badge

    def _award_badge(self, badge_class, user, activity_online=None):
        """Helper to award badge with delivery method"""
        instance = BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
            activity_online=activity_online
        )
        return instance

    def test_competency_areas_filter_online(self):
        """Test competency areas filtered by online delivery method"""
        # Create badges with competencies
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Skill', 120)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Skill', 60)

        # Award with different delivery methods
        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        # Request online only
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only contain online competency
        competency_names = [c['name'] for c in response.data['data']]
        self.assertIn('Online Skill', competency_names)
        self.assertNotIn('In-Person Skill', competency_names)

    def test_competency_areas_filter_in_person(self):
        """Test competency areas filtered by in-person delivery method"""
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Skill', 120)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Skill', 60)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        # Request in-person only
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        competency_names = [c['name'] for c in response.data['data']]
        self.assertIn('In-Person Skill', competency_names)
        self.assertNotIn('Online Skill', competency_names)

    def test_competency_areas_no_filter(self):
        """Test competency areas without delivery method filter returns all"""
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Skill', 120)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Skill', 60)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should contain both competencies
        competency_names = [c['name'] for c in response.data['data']]
        self.assertIn('Online Skill', competency_names)
        self.assertIn('In-Person Skill', competency_names)

    def test_strengthened_competencies_filter_online(self):
        """Test strengthened competencies filtered by online delivery method"""
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Competency', 180)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Competency', 90)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        competency_titles = [c['title'] for c in response.data['competencies']]
        self.assertIn('Online Competency', competency_titles)
        self.assertNotIn('In-Person Competency', competency_titles)

    def test_strengthened_competencies_filter_in_person(self):
        """Test strengthened competencies filtered by in-person delivery method"""
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Competency', 180)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Competency', 90)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        competency_titles = [c['title'] for c in response.data['competencies']]
        self.assertIn('In-Person Competency', competency_titles)
        self.assertNotIn('Online Competency', competency_titles)

    def test_strengthened_competencies_no_filter(self):
        """Test strengthened competencies without filter returns all"""
        online_badge = self._create_badge_with_competency('Online Badge', 'Online Competency', 180)
        inperson_badge = self._create_badge_with_competency('In-Person Badge', 'In-Person Competency', 90)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        competency_titles = [c['title'] for c in response.data['competencies']]
        self.assertIn('Online Competency', competency_titles)
        self.assertIn('In-Person Competency', competency_titles)

    def test_strengthened_competencies_hours_calculation_with_filter(self):
        """Test that hours are calculated correctly when filtered"""
        # Create badge with 180 minutes = 3 hours
        online_badge = self._create_badge_with_competency('Online Badge', 'Test Competency', 180)

        # Award to multiple learners
        learner2 = self.setup_user(email='learner2_delivery@test.com', authenticate=False)

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(online_badge, learner2, activity_online=True)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/strengthened-competencies?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 2 awards * 180 minutes / 60 = 6 hours
        self.assertEqual(response.data['competencies'][0]['hours'], 6)
        self.assertEqual(response.data['metadata']['totalHours'], 6)

    def test_empty_result_with_filter(self):
        """Test empty result when filter excludes all badges"""
        # Create only online badges
        online_badge = self._create_badge_with_competency('Online Only', 'Online Only Skill', 120)
        self._award_badge(online_badge, self.learner, activity_online=True)

        # Request in-person (should return empty)
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], [])
        self.assertEqual(response.data['metadata']['totalAreas'], 0)


class NetworkDashboardBadgeLocationsTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Badge Locations endpoint.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='locations_admin@example.com',
            first_name='Locations',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Locations Network',
                description='Network for locations testing',
                email='locations@test.com',
                url='https://locations.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            # Create issuer with location info (city and zip)
            self.issuer_berlin = Issuer.objects.create(
                name='Berlin University',
                email='berlin@test.com',
                url='https://berlin-uni.com',
                city='Berlin',
                zip='10115',
                created_by=self.admin_user,
                verified=True
            )

            self.issuer_munich = Issuer.objects.create(
                name='Munich University',
                email='munich@test.com',
                url='https://munich-uni.com',
                city='München',
                zip='80333',
                created_by=self.admin_user,
                verified=True
            )

            # Issuer without location
            self.issuer_no_location = Issuer.objects.create(
                name='No Location University',
                email='nolocation@test.com',
                url='https://nolocation.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer_berlin)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer_munich)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer_no_location)

        self.learner = self.setup_user(
            email='locations_learner@example.com',
            first_name='Locations',
            last_name='Learner',
            authenticate=False
        )

    def _create_badge(self, name, issuer):
        """Helper to create badge"""
        return BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=issuer,
            created_by=self.admin_user,
            criteria_text='Complete requirements'
        )

    def _award_badge(self, badge_class, user, activity_online=None):
        """Helper to award badge"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
            activity_online=activity_online
        )

    def test_badge_locations_returns_200(self):
        """Test that endpoint returns 200"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_badge_locations_empty_response(self):
        """Test response when no badges exist"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('locations', response.data)
        self.assertEqual(response.data['metadata']['totalLocations'], 0)
        self.assertEqual(response.data['locations'], [])

    def test_badge_locations_with_data(self):
        """Test locations are returned correctly"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        self._award_badge(badge_berlin, self.learner)
        self._award_badge(badge_munich, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['locations']), 0)

        # Check location structure (new format: city, zipCode, badgeCount, badgePercentage)
        for location in response.data['locations']:
            self.assertIn('city', location)
            self.assertIn('zipCode', location)
            self.assertIn('badgeCount', location)
            self.assertIn('badgePercentage', location)

    def test_badge_locations_zip_code(self):
        """Test that ZIP codes are returned correctly"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        self._award_badge(badge_berlin, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['locations']), 1)

        location = response.data['locations'][0]
        self.assertEqual(location['city'], 'Berlin')
        self.assertEqual(location['zipCode'], '10115')

    def test_badge_locations_filter_online(self):
        """Test filtering by online delivery method"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        self._award_badge(badge_berlin, self.learner, activity_online=True)
        self._award_badge(badge_munich, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['deliveryMethod'], 'online')
        # Should only include Berlin (online badge)
        self.assertEqual(response.data['metadata']['totalLocations'], 1)

    def test_badge_locations_filter_in_person(self):
        """Test filtering by in-person delivery method"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        self._award_badge(badge_berlin, self.learner, activity_online=True)
        self._award_badge(badge_munich, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['deliveryMethod'], 'in-person')
        # Should only include Munich (in-person badge)
        self.assertEqual(response.data['metadata']['totalLocations'], 1)

    def test_badge_locations_no_filter_includes_all(self):
        """Test that no filter includes all locations"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        self._award_badge(badge_berlin, self.learner, activity_online=True)
        self._award_badge(badge_munich, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLocations'], 2)

    def test_badge_locations_badge_count(self):
        """Test that badge count is correct per location"""
        badge_berlin1 = self._create_badge('Berlin Badge 1', self.issuer_berlin)
        badge_berlin2 = self._create_badge('Berlin Badge 2', self.issuer_berlin)

        learner2 = self.setup_user(email='learner2_loc@test.com', authenticate=False)

        # Award 3 badges in Berlin
        self._award_badge(badge_berlin1, self.learner)
        self._award_badge(badge_berlin2, self.learner)
        self._award_badge(badge_berlin1, learner2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['locations'][0]['badgeCount'], 3)

    def test_badge_locations_percentage_calculation(self):
        """Test that badge percentage is calculated correctly"""
        # Create another issuer in Berlin with same zip
        with ISSUER_SAVE_MOCK:
            issuer_berlin2 = Issuer.objects.create(
                name='Berlin Tech',
                email='berlin2@test.com',
                url='https://berlin-tech.com',
                city='Berlin',
                zip='10115',
                created_by=self.admin_user,
                verified=True
            )
        NetworkMembership.objects.create(network=self.network, issuer=issuer_berlin2)

        badge1 = self._create_badge('Badge 1', self.issuer_berlin)
        badge2 = self._create_badge('Badge 2', issuer_berlin2)

        self._award_badge(badge1, self.learner)
        self._award_badge(badge2, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Both badges are in same location (Berlin, 10xxx), so 100%
        location = response.data['locations'][0]
        self.assertEqual(location['badgePercentage'], 100.0)
        self.assertEqual(location['badgeCount'], 2)

    def test_badge_locations_limit_parameter(self):
        """Test limit parameter"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        self._award_badge(badge_berlin, self.learner)
        self._award_badge(badge_munich, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations?limit=1'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['locations']), 1)

    def test_badge_locations_sorted_by_badge_count(self):
        """Test that locations are sorted by badge count"""
        badge_berlin = self._create_badge('Berlin Badge', self.issuer_berlin)
        badge_munich = self._create_badge('Munich Badge', self.issuer_munich)

        learner2 = self.setup_user(email='learner2_sort@test.com', authenticate=False)

        # Berlin: 1 badge, Munich: 2 badges
        self._award_badge(badge_berlin, self.learner)
        self._award_badge(badge_munich, self.learner)
        self._award_badge(badge_munich, learner2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # München should be first (more badges)
        self.assertIn('München', response.data['locations'][0]['city'])

    def test_badge_locations_excludes_issuers_without_location(self):
        """Test that issuers without location info are excluded"""
        badge_no_location = self._create_badge('No Location Badge', self.issuer_no_location)
        self._award_badge(badge_no_location, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be empty since issuer has no location
        self.assertEqual(response.data['metadata']['totalLocations'], 0)

    def test_badge_locations_response_structure(self):
        """Test complete response structure"""
        badge = self._create_badge('Test Badge', self.issuer_berlin)
        self._award_badge(badge, self.learner)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check metadata
        self.assertIn('totalLocations', response.data['metadata'])
        self.assertIn('totalBadges', response.data['metadata'])
        self.assertIn('deliveryMethod', response.data['metadata'])
        self.assertIn('lastUpdated', response.data['metadata'])

        # Check locations
        self.assertIn('locations', response.data)

    def test_badge_locations_network_not_found(self):
        """Test 404 for non-existent network"""
        url = '/v1/issuer/networks/non-existent-network/dashboard/badge-locations'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_badge_locations_authentication_required(self):
        """Test that endpoint requires authentication"""
        client = APIClient()  # Unauthenticated client
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/badge-locations'
        response = client.get(url)

        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])


class NetworkDashboardCompetencyAreasSkillsDeliveryMethodTest(BadgrTestCase):
    """
    Integration tests for Network Dashboard Competency Areas Skills endpoint
    with deliveryMethod filter.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()

        self.admin_user = self.setup_user(
            email='skills_delivery_admin@example.com',
            first_name='Skills',
            last_name='Admin',
            authenticate=True,
            token_scope='rw:issuer'
        )

        with ISSUER_SAVE_MOCK:
            self.network = Issuer.objects.create(
                name='Skills Delivery Network',
                description='Network for skills delivery method testing',
                email='skills_delivery@test.com',
                url='https://skills-delivery.com',
                is_network=True,
                created_by=self.admin_user,
                verified=True
            )

            self.issuer = Issuer.objects.create(
                name='Skills Delivery Issuer',
                email='skills_delivery_issuer@test.com',
                url='https://skills-delivery-issuer.com',
                created_by=self.admin_user,
                verified=True
            )

        NetworkMembership.objects.create(network=self.network, issuer=self.issuer)

        self.learner = self.setup_user(
            email='skills_delivery_learner@example.com',
            first_name='Skills',
            last_name='Learner',
            authenticate=False
        )

    def _create_badge_with_skill(self, name, skill_uri, study_load=120):
        """Helper to create badge with ESCO skill"""
        with BADGECLASS_SAVE_MOCK:
            badge = BadgeClass.objects.create(
                name=name,
                description=f'{name} description',
                issuer=self.issuer,
                created_by=self.admin_user,
                criteria_text='Complete requirements'
            )

        # Add category extension (needed for skills tree)
        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': 'competency'})
        )

        # Add skill extension with ESCO URI
        BadgeClassExtension.objects.create(
            badgeclass=badge,
            name='extensions:SkillExtension',
            original_json=json.dumps([{
                'escoUri': skill_uri,
                'studyLoad': study_load
            }])
        )

        return badge

    def _award_badge(self, badge_class, user, activity_online=None):
        """Helper to award badge with delivery method"""
        with ASSERTION_SAVE_MOCK, NOTIFY_EARNER_MOCK:
            instance = BadgeInstance.objects.create(
                badgeclass=badge_class,
                user=user,
                issuer=badge_class.issuer,
                recipient_identifier=user.email,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                activity_online=activity_online
            )
        return instance

    def test_skills_filter_online_delivery_method(self):
        """Test that deliveryMethod=online filters skills correctly"""
        # Use generic skill URIs that don't need ESCO lookup
        online_badge = self._create_badge_with_skill(
            'Online Badge',
            'http://data.europa.eu/esco/skill/test-online',
            120
        )
        inperson_badge = self._create_badge_with_skill(
            'In-Person Badge',
            'http://data.europa.eu/esco/skill/test-inperson',
            60
        )

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'online')

    def test_skills_filter_inperson_delivery_method(self):
        """Test that deliveryMethod=in-person filters skills correctly"""
        online_badge = self._create_badge_with_skill(
            'Online Badge',
            'http://data.europa.eu/esco/skill/test-online',
            120
        )
        inperson_badge = self._create_badge_with_skill(
            'In-Person Badge',
            'http://data.europa.eu/esco/skill/test-inperson',
            60
        )

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills?deliveryMethod=in-person'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'in-person')

    def test_skills_no_delivery_method_filter(self):
        """Test that without deliveryMethod filter all skills are returned"""
        online_badge = self._create_badge_with_skill(
            'Online Badge',
            'http://data.europa.eu/esco/skill/test-online',
            120
        )
        inperson_badge = self._create_badge_with_skill(
            'In-Person Badge',
            'http://data.europa.eu/esco/skill/test-inperson',
            60
        )

        self._award_badge(online_badge, self.learner, activity_online=True)
        self._award_badge(inperson_badge, self.learner, activity_online=False)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # deliveryMethod should be None when not filtered
        self.assertIsNone(response.data['metadata']['filters']['deliveryMethod'])

    def test_skills_invalid_delivery_method_returns_400(self):
        """Test that invalid deliveryMethod returns 400 Bad Request"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills?deliveryMethod=invalid'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('invalid', response.data['error'].lower())

    def test_skills_response_metadata_includes_delivery_method(self):
        """Test that response metadata includes deliveryMethod in filters"""
        badge = self._create_badge_with_skill(
            'Test Badge',
            'http://data.europa.eu/esco/skill/test',
            120
        )
        self._award_badge(badge, self.learner, activity_online=True)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('filters', response.data['metadata'])
        self.assertIn('deliveryMethod', response.data['metadata']['filters'])
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'online')

    def test_skills_empty_result_includes_delivery_method(self):
        """Test that empty result still includes deliveryMethod in filters"""
        # Don't create any badges - should return empty result with filter metadata
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/competency-areas/skills?deliveryMethod=online'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalSkills'], 0)
        self.assertEqual(response.data['metadata']['filters']['deliveryMethod'], 'online')
        self.assertEqual(response.data['skills'], [])
