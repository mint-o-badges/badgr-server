# encoding: utf-8
"""
Unit and Integration Tests for Network Dashboard Learners API endpoints.

Tests the following endpoints:
- GET /v1/issuer/networks/{networkSlug}/dashboard/learners
- GET /v1/issuer/networks/{networkSlug}/dashboard/learners/residence
- GET /v1/issuer/networks/{networkSlug}/dashboard/learners/residence/{zipCode}
- GET /v1/issuer/networks/{networkSlug}/dashboard/learners/gender
- GET /v1/issuer/networks/{networkSlug}/dashboard/learners/gender/{gender}

These tests verify:
1. Data accuracy and plausibility
2. Residence distribution calculations
3. Gender distribution calculations
4. Drill-down detail views (by region and gender)
5. Edge cases (empty data, unknown regions, etc.)
6. Authentication and authorization
7. Error handling
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
)
from mainsite.tests.base import BadgrTestCase

import json


def mock_issuer_save(self, *args, **kwargs):
    """Override Issuer.save to skip geocoding for tests"""
    from django.db.models import Model
    super(Issuer, self).save(*args, **kwargs)


def mock_badgeinstance_save(self, *args, **kwargs):
    """Override BadgeInstance.save to skip image processing for tests"""
    from django.db.models import Model
    # Skip the image processing in the original save method
    # Call the parent's parent save to avoid image requirements
    from mainsite.mixins import ResizeUploadedImage
    from entity.models import _AbstractVersionedEntity
    from cachemodel.models import CacheModel
    # Set entity_id if not set
    if not self.entity_id:
        import uuid
        self.entity_id = str(uuid.uuid4()).replace('-', '')[:16]
    CacheModel.save(self, *args, **kwargs)


def mock_notify_earner(self, *args, **kwargs):
    """Skip notify_earner for tests"""
    pass


ISSUER_SAVE_MOCK = patch('issuer.models.Issuer.save', mock_issuer_save)
BADGEINSTANCE_SAVE_MOCK = patch('issuer.models.BadgeInstance.save', mock_badgeinstance_save)
NOTIFY_EARNER_MOCK = patch('issuer.models.BadgeInstance.notify_earner', mock_notify_earner)


class NetworkDashboardLearnersBaseTest(BadgrTestCase):
    """
    Base test class with common fixtures for Learners API tests.
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

        # Add issuers to network
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer1)
        NetworkMembership.objects.create(network=self.network, issuer=self.issuer2)

        # Create learner users with different attributes
        # Using proper first names that gender-guesser library can detect
        self.learner1 = self.setup_user(
            email='learner1@example.com',
            first_name='Michael',  # Male name for gender-guesser
            last_name='One',
            authenticate=False
        )
        self.learner1.zip_code = '80331'  # München PLZ
        self.learner1.save()

        self.learner2 = self.setup_user(
            email='learner2@example.com',
            first_name='Maria',  # Female name for gender-guesser
            last_name='Two',
            authenticate=False
        )
        self.learner2.zip_code = '80333'  # München PLZ
        self.learner2.save()

        self.learner3 = self.setup_user(
            email='learner3@example.com',
            first_name='Thomas',  # Male name for gender-guesser
            last_name='Three',
            authenticate=False
        )
        self.learner3.zip_code = '10115'  # Berlin PLZ
        self.learner3.save()

        self.learner4 = self.setup_user(
            email='learner4@example.com',
            first_name='Anna',  # Female name for gender-guesser
            last_name='Four',
            authenticate=False
        )
        self.learner4.zip_code = '20095'  # Hamburg PLZ
        self.learner4.save()

        self.learner5 = self.setup_user(
            email='learner5@example.com',
            first_name='',  # No name -> noAnswer
            last_name='Five',
            authenticate=False
        )
        self.learner5.zip_code = ''  # No zip
        self.learner5.save()

    def _create_badge_class(self, issuer, name, category=None, competencies=None):
        """Helper to create a badge class with optional extensions"""
        badge_class = BadgeClass.objects.create(
            name=name,
            description=f'{name} description',
            issuer=issuer,
            created_by=self.admin_user,
            criteria_text='Complete the course'
        )

        # Always create CategoryExtension (required by BadgeInstance manager)
        # original_json needs to be a JSON string
        BadgeClassExtension.objects.create(
            badgeclass=badge_class,
            name='extensions:CategoryExtension',
            original_json=json.dumps({'Category': category or 'participation'})
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
        with BADGEINSTANCE_SAVE_MOCK, NOTIFY_EARNER_MOCK:
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


class NetworkDashboardLearnersOverviewTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for the /dashboard/learners endpoint.
    """

    def test_learners_overview_returns_correct_structure(self):
        """Test that the overview response has correct structure"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('kpis', response.data)
        self.assertIn('residenceDistribution', response.data)
        self.assertIn('genderDistribution', response.data)

        # Check KPIs structure with trend data
        kpis = response.data['kpis']
        self.assertIn('totalLearners', kpis)
        self.assertIn('totalCompetencyHours', kpis)

        # Check that each KPI has the new structure with value and trend data
        total_learners = kpis['totalLearners']
        self.assertIn('value', total_learners)
        self.assertIn('trend', total_learners)
        self.assertIn('trendValue', total_learners)
        self.assertIn('trendPeriod', total_learners)

        total_hours = kpis['totalCompetencyHours']
        self.assertIn('value', total_hours)
        self.assertIn('trend', total_hours)
        self.assertIn('trendValue', total_hours)
        self.assertIn('trendPeriod', total_hours)

    def test_learners_overview_total_learners_count(self):
        """Test that totalLearners returns unique users with badges"""
        badge1 = self._create_badge_class(self.issuer1, 'Badge 1')
        badge2 = self._create_badge_class(self.issuer1, 'Badge 2')

        # Award multiple badges to same user (should count as 1 learner)
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge2, self.learner1)

        # Award to other learners
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge1, self.learner3)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kpis']['totalLearners']['value'], 3)

    def test_learners_overview_competency_hours(self):
        """Test that totalCompetencyHours is calculated correctly"""
        competencies = [
            {'name': 'Skill A', 'studyLoad': 120},  # 2 hours
            {'name': 'Skill B', 'studyLoad': 60},   # 1 hour
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Hours Badge', competencies=competencies
        )

        # Award to 2 users = 2 * 3 hours = 6 hours
        self._award_badge(badge, self.learner1)
        self._award_badge(badge, self.learner2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kpis']['totalCompetencyHours']['value'], 6)

    def test_learners_overview_residence_distribution(self):
        """Test that residence distribution is returned correctly"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Award badges to learners with different PLZ codes
        self._award_badge(badge, self.learner1)  # 80331 (München)
        self._award_badge(badge, self.learner2)  # 80333 (München)
        self._award_badge(badge, self.learner3)  # 10115 (Berlin)
        self._award_badge(badge, self.learner4)  # 20095 (Hamburg)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        residence = response.data['residenceDistribution']
        # Residence distribution should be a list
        self.assertIsInstance(residence, list)

        # Each entry should have the correct structure
        for entry in residence:
            self.assertIn('city', entry)
            self.assertIn('learnerCount', entry)
            self.assertIn('percentage', entry)
            self.assertIsInstance(entry['city'], str)
            self.assertGreaterEqual(entry['learnerCount'], 0)
            self.assertGreaterEqual(entry['percentage'], 0)
            self.assertLessEqual(entry['percentage'], 100)

    def test_learners_overview_gender_distribution(self):
        """Test that gender distribution counts correctly"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Award badges to learners with different genders
        # Names are: Michael (male), Maria (female), Thomas (male), Anna (female), '' (noAnswer)
        self._award_badge(badge, self.learner1)  # Michael -> male
        self._award_badge(badge, self.learner2)  # Maria -> female
        self._award_badge(badge, self.learner3)  # Thomas -> male
        self._award_badge(badge, self.learner4)  # Anna -> female
        self._award_badge(badge, self.learner5)  # '' -> noAnswer

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        gender = response.data['genderDistribution']

        # Find male entry (gender-guesser detects Michael and Thomas as male)
        male = next((g for g in gender if g['gender'] == 'male'), None)
        self.assertIsNotNone(male)
        self.assertEqual(male['count'], 2)

        # Find female entry (gender-guesser detects Maria and Anna as female)
        female = next((g for g in gender if g['gender'] == 'female'), None)
        self.assertIsNotNone(female)
        self.assertEqual(female['count'], 2)

    def test_learners_overview_empty_network(self):
        """Test overview for network with no badges"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kpis']['totalLearners']['value'], 0)
        self.assertEqual(response.data['kpis']['totalCompetencyHours']['value'], 0)
        self.assertEqual(response.data['residenceDistribution'], [])
        self.assertEqual(response.data['genderDistribution'], [])

    def test_learners_overview_network_not_found(self):
        """Test 404 for non-existent network"""
        url = '/v1/issuer/networks/nonexistent123/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_learners_overview_trend_values_valid(self):
        """Test that trend values are valid enum values"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = response.data['kpis']

        # Check totalLearners trend
        learner_trend = kpis['totalLearners']['trend']
        self.assertIn(learner_trend, ['up', 'down', 'stable'])

        # Check totalCompetencyHours trend
        hours_trend = kpis['totalCompetencyHours']['trend']
        self.assertIn(hours_trend, ['up', 'down', 'stable'])

        # Check trendPeriod is set
        self.assertEqual(kpis['totalLearners']['trendPeriod'], 'lastMonth')
        self.assertEqual(kpis['totalCompetencyHours']['trendPeriod'], 'lastMonth')

    def test_learners_overview_trend_up_when_new_badges(self):
        """Test that trend shows 'up' when badges are from last 30 days only"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Award badges today (within last 30 days)
        self._award_badge(badge, self.learner1)
        self._award_badge(badge, self.learner2)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # With no previous 30 days data, trend should be 'up'
        # trendValue is the absolute count (2 learners gained vs 0 previous)
        kpis = response.data['kpis']
        self.assertEqual(kpis['totalLearners']['trend'], 'up')
        self.assertEqual(kpis['totalLearners']['trendValue'], 2)

    def test_learners_overview_trend_stable_with_equal_activity(self):
        """Test trend is stable when activity is equal in both periods"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Create badges from 30-60 days ago (previous period)
        forty_five_days_ago = timezone.now() - timedelta(days=45)
        self._award_badge(badge, self.learner1, created_at=forty_five_days_ago)
        self._award_badge(badge, self.learner2, created_at=forty_five_days_ago)

        # Award same number of badges in the last 30 days (current period)
        self._award_badge(badge, self.learner3)
        self._award_badge(badge, self.learner4)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = response.data['kpis']
        # Value should be 4 (all learners)
        self.assertEqual(kpis['totalLearners']['value'], 4)
        # Trend compares current 30 days (2) vs previous 30 days (2) = stable
        self.assertEqual(kpis['totalLearners']['trend'], 'stable')
        self.assertEqual(kpis['totalLearners']['trendValue'], 0)

    def test_learners_overview_trend_down(self):
        """Test trend shows 'down' when previous period had more activity"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Create more badges in previous 30-60 days period
        forty_five_days_ago = timezone.now() - timedelta(days=45)
        self._award_badge(badge, self.learner1, created_at=forty_five_days_ago)
        self._award_badge(badge, self.learner2, created_at=forty_five_days_ago)
        self._award_badge(badge, self.learner3, created_at=forty_five_days_ago)

        # Award fewer badges in last 30 days (only 1)
        self._award_badge(badge, self.learner4)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total learners is cumulative = 4
        self.assertEqual(response.data['kpis']['totalLearners']['value'], 4)
        # Trend compares 1 (current) vs 3 (previous) = down by 2
        self.assertEqual(response.data['kpis']['totalLearners']['trend'], 'down')
        self.assertEqual(response.data['kpis']['totalLearners']['trendValue'], 2)

    def test_learners_overview_trend_value_is_positive(self):
        """Test that trendValue is always positive (direction is in trend field)"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = response.data['kpis']
        # trendValue should always be >= 0
        self.assertGreaterEqual(kpis['totalLearners']['trendValue'], 0)
        self.assertGreaterEqual(kpis['totalCompetencyHours']['trendValue'], 0)


class NetworkDashboardLearnersResidenceTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for the /dashboard/learners/residence endpoint.
    """

    def test_residence_distribution_returns_correct_structure(self):
        """Test that residence response has correct structure"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('statistics', response.data)

        metadata = response.data['metadata']
        self.assertIn('totalLearners', metadata)
        self.assertIn('totalRegions', metadata)
        self.assertIn('lastUpdated', metadata)

    def test_residence_distribution_limit_parameter(self):
        """Test that limit parameter controls number of regions returned"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Award badges to learners from different cities
        self._award_badge(badge, self.learner1)  # München
        self._award_badge(badge, self.learner2)  # München
        self._award_badge(badge, self.learner3)  # Berlin
        self._award_badge(badge, self.learner4)  # Hamburg
        self._award_badge(badge, self.learner5)  # Unbekannt

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence?limit=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stats = response.data['statistics']
        # Should have 2 individual regions + 1 "Other" category
        non_other = [s for s in stats if not s['isOtherCategory']]
        other = [s for s in stats if s['isOtherCategory']]

        self.assertEqual(len(non_other), 2)
        self.assertEqual(len(other), 1)

    def test_residence_distribution_include_other_parameter(self):
        """Test that includeOther parameter works"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        self._award_badge(badge, self.learner1)  # München
        self._award_badge(badge, self.learner3)  # Berlin
        self._award_badge(badge, self.learner4)  # Hamburg

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence?limit=1&includeOther=false'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stats = response.data['statistics']
        # Should have only 1 region, no "Other"
        other = [s for s in stats if s['isOtherCategory']]
        self.assertEqual(len(other), 0)

    def test_residence_distribution_empty_network(self):
        """Test residence endpoint for network with no learners"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 0)
        self.assertEqual(response.data['statistics'], [])


class NetworkDashboardLearnersResidenceDetailTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for the /dashboard/learners/residence/{zipCode} endpoint.
    """

    def test_residence_detail_returns_correct_structure(self):
        """Test that residence detail response has correct structure"""
        competencies = [
            {'name': 'Python', 'studyLoad': 120, 'category': 'Programming'},
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Test Badge', competencies=competencies
        )
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/München'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('topCompetencyAreas', response.data)
        self.assertIn('topStrengthenedCompetencies', response.data)

        metadata = response.data['metadata']
        self.assertIn('zipCode', metadata)
        self.assertIn('regionName', metadata)
        self.assertIn('totalLearners', metadata)

    def test_residence_detail_by_city_name(self):
        """Test residence detail lookup by city name"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # München
        self._award_badge(badge, self.learner2)  # München

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/München'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 2)
        self.assertEqual(response.data['metadata']['regionName'], 'München')

    def test_residence_detail_by_zip_prefix(self):
        """Test residence detail lookup by ZIP code prefix"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # München 80331
        self._award_badge(badge, self.learner2)  # München 80333

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/80xxx'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 2)

    def test_residence_detail_competencies(self):
        """Test that competencies are returned correctly"""
        competencies = [
            {'name': 'Python Programming', 'studyLoad': 120, 'category': 'Programming'},
            {'name': 'Data Analysis', 'studyLoad': 60, 'category': 'Analytics'},
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Tech Badge', competencies=competencies
        )
        self._award_badge(badge, self.learner1)  # München

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/München'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check strengthened competencies
        competencies = response.data['topStrengthenedCompetencies']
        self.assertGreater(len(competencies), 0)

        python = next((c for c in competencies if 'python' in c['competencyId'].lower()), None)
        self.assertIsNotNone(python)
        self.assertIn('title', python)
        self.assertIn('hours', python)

    def test_residence_detail_region_not_found(self):
        """Test 404 for non-existent region"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # München

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/UnknownCity'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NetworkDashboardLearnersGenderTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for the /dashboard/learners/gender endpoint.
    """

    def test_gender_distribution_returns_correct_structure(self):
        """Test that gender response has correct structure"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('distribution', response.data)

        metadata = response.data['metadata']
        self.assertIn('totalLearners', metadata)
        self.assertIn('lastUpdated', metadata)

    def test_gender_distribution_counts(self):
        """Test that gender counts are correct"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')

        # Names: Michael (male), Maria (female), Thomas (male), Anna (female), '' (noAnswer)
        self._award_badge(badge, self.learner1)  # Michael -> male
        self._award_badge(badge, self.learner2)  # Maria -> female
        self._award_badge(badge, self.learner3)  # Thomas -> male
        self._award_badge(badge, self.learner4)  # Anna -> female
        self._award_badge(badge, self.learner5)  # '' -> noAnswer

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 5)

        dist = response.data['distribution']

        # gender-guesser: Michael and Thomas are male
        male = next((g for g in dist if g['gender'] == 'male'), None)
        self.assertIsNotNone(male)
        self.assertEqual(male['count'], 2)
        self.assertEqual(male['percentage'], 40.0)

        # gender-guesser: Maria and Anna are female
        female = next((g for g in dist if g['gender'] == 'female'), None)
        self.assertIsNotNone(female)
        self.assertEqual(female['count'], 2)

        # learner5 with empty first_name -> noAnswer
        no_answer = next((g for g in dist if g['gender'] == 'noAnswer'), None)
        self.assertIsNotNone(no_answer)
        self.assertEqual(no_answer['count'], 1)

    def test_gender_distribution_labels(self):
        """Test that gender labels are localized"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # male

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        dist = response.data['distribution']
        male = next((g for g in dist if g['gender'] == 'male'), None)
        self.assertEqual(male['genderLabel'], 'Männlich')

    def test_gender_distribution_empty_network(self):
        """Test gender endpoint for network with no learners"""
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 0)
        self.assertEqual(response.data['distribution'], [])


class NetworkDashboardLearnersGenderDetailTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for the /dashboard/learners/gender/{gender} endpoint.
    """

    def test_gender_detail_returns_correct_structure(self):
        """Test that gender detail response has correct structure"""
        competencies = [
            {'name': 'Python', 'studyLoad': 120, 'category': 'Programming'},
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Test Badge', competencies=competencies
        )
        self._award_badge(badge, self.learner1)  # Michael -> male

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metadata', response.data)
        self.assertIn('topKompetenzbereiche', response.data)
        self.assertIn('topEinzelkompetenzen', response.data)
        self.assertIn('topBadges', response.data)

        metadata = response.data['metadata']
        self.assertIn('gender', metadata)
        self.assertIn('genderLabel', metadata)
        self.assertIn('totalLearners', metadata)
        self.assertIn('totalBadges', metadata)

    def test_gender_detail_male(self):
        """Test gender detail for male learners"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # Michael -> male
        self._award_badge(badge, self.learner3)  # Thomas -> male

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 2)
        self.assertEqual(response.data['metadata']['gender'], 'male')
        self.assertEqual(response.data['metadata']['genderLabel'], 'Männlich')

    def test_gender_detail_female(self):
        """Test gender detail for female learners"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner2)  # Maria -> female

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/female'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 1)
        self.assertEqual(response.data['metadata']['gender'], 'female')
        self.assertEqual(response.data['metadata']['genderLabel'], 'Weiblich')

    def test_gender_detail_diverse(self):
        """Test gender detail for diverse learners - gender-guesser doesn't detect diverse"""
        # Note: gender-guesser library doesn't detect 'diverse' gender,
        # it only returns male/female/unknown. So diverse category will be empty
        # unless users explicitly have that setting (which is not supported here).
        # This test verifies the endpoint handles the diverse category correctly.
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # Michael (won't be diverse)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/diverse'
        response = self.client.get(url)

        # Should return 404 if no diverse learners found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_gender_detail_no_answer(self):
        """Test gender detail for noAnswer learners"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner5)  # empty first_name -> noAnswer

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/noAnswer'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['totalLearners'], 1)
        self.assertEqual(response.data['metadata']['genderLabel'], 'Keine Angabe')

    def test_gender_detail_localized_parameter(self):
        """Test gender detail with localized parameter (German)"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner2)  # Maria -> female

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/weiblich'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['gender'], 'female')

    def test_gender_detail_top_badges(self):
        """Test that top badges are returned correctly"""
        badge1 = self._create_badge_class(self.issuer1, 'Badge One')
        badge2 = self._create_badge_class(self.issuer1, 'Badge Two')

        # Award badges to male learners
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner1)  # Same badge twice
        self._award_badge(badge2, self.learner1)
        self._award_badge(badge1, self.learner3)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        top_badges = response.data['topBadges']
        self.assertGreater(len(top_badges), 0)

        # Badge One should be first (3 awards)
        self.assertEqual(top_badges[0]['name'], 'Badge One')
        self.assertEqual(top_badges[0]['count'], 3)

    def test_gender_detail_top_competencies(self):
        """Test that top competencies are returned correctly"""
        competencies = [
            {'name': 'Python Programming', 'studyLoad': 120, 'category': 'Programming'},
            {'name': 'Data Analysis', 'studyLoad': 60, 'category': 'Analytics'},
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Tech Badge', competencies=competencies
        )
        self._award_badge(badge, self.learner1)  # male
        self._award_badge(badge, self.learner3)  # male

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        einzelkompetenzen = response.data['topEinzelkompetenzen']
        self.assertGreater(len(einzelkompetenzen), 0)

        # Each competency should have count, hours, etc.
        for comp in einzelkompetenzen:
            self.assertIn('competencyId', comp)
            self.assertIn('name', comp)
            self.assertIn('count', comp)
            self.assertIn('hours', comp)

    def test_gender_detail_invalid_gender(self):
        """Test 404 for invalid gender category"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/invalid'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_gender_detail_no_learners(self):
        """Test 404 when no learners found for gender"""
        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)  # male only

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/female'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_gender_detail_limit_parameters(self):
        """Test competencyLimit and badgeLimit parameters"""
        competencies = [
            {'name': f'Competency {i}', 'studyLoad': 60}
            for i in range(10)
        ]
        badge = self._create_badge_class(
            self.issuer1, 'Badge', competencies=competencies
        )
        self._award_badge(badge, self.learner1)

        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male?competencyLimit=3&badgeLimit=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should respect limits
        self.assertLessEqual(len(response.data['topEinzelkompetenzen']), 3)
        self.assertLessEqual(len(response.data['topBadges']), 2)

    def test_gender_detail_top_badges_limited(self):
        """
        Test that topBadges returns only the top N badges (no "other" category).
        totalBadges in metadata still counts all badges.
        """
        # Create multiple badge classes
        badge1 = self._create_badge_class(self.issuer1, 'Badge One')
        badge2 = self._create_badge_class(self.issuer1, 'Badge Two')
        badge3 = self._create_badge_class(self.issuer1, 'Badge Three')
        badge4 = self._create_badge_class(self.issuer1, 'Badge Four')
        badge5 = self._create_badge_class(self.issuer1, 'Badge Five')
        badge6 = self._create_badge_class(self.issuer1, 'Badge Six')

        # Award badges to male learners (learner1 and learner3 are male)
        # Badge One: 5 awards
        for _ in range(5):
            self._award_badge(badge1, self.learner1)

        # Badge Two: 4 awards
        for _ in range(4):
            self._award_badge(badge2, self.learner1)

        # Badge Three: 3 awards
        for _ in range(3):
            self._award_badge(badge3, self.learner3)

        # Badge Four: 2 awards
        for _ in range(2):
            self._award_badge(badge4, self.learner3)

        # Badge Five: 1 award
        self._award_badge(badge5, self.learner1)

        # Badge Six: 1 award
        self._award_badge(badge6, self.learner3)

        # Total badges: 5+4+3+2+1+1 = 16
        expected_total_badges = 16

        # Test with badgeLimit=5 (should return only top 5 badges, no "other")
        url = f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male?badgeLimit=5'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check totalBadges in metadata counts ALL badges
        total_badges_metadata = response.data['metadata']['totalBadges']
        self.assertEqual(total_badges_metadata, expected_total_badges)

        # topBadges should contain only the limited number of badges
        top_badges = response.data['topBadges']
        self.assertLessEqual(len(top_badges), 5)

        # Verify no "other" category exists
        other_badge = next((b for b in top_badges if b['badgeId'] == 'other'), None)
        self.assertIsNone(other_badge, "Should NOT include 'other' category")


class NetworkDashboardLearnersAuthorizationTest(NetworkDashboardLearnersBaseTest):
    """
    Tests for authentication and authorization on Learners endpoints.
    """

    def test_unauthenticated_request_fails(self):
        """Test that unauthenticated requests fail"""
        # Clear authentication
        self.client.credentials()

        badge = self._create_badge_class(self.issuer1, 'Test Badge')
        self._award_badge(badge, self.learner1)

        endpoints = [
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners',
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence',
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/residence/München',
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender',
            f'/v1/issuer/networks/{self.network.entity_id}/dashboard/learners/gender/male',
        ]

        for url in endpoints:
            response = self.client.get(url)
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                f"Endpoint {url} should require authentication"
            )
