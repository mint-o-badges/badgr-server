# encoding: utf-8
"""
Test suite for userCount in topInstitutions response.

Verifies that:
1. userCount is present in topInstitutions
2. userCount reflects unique users per institution
3. statistics.totalUsers matches the sum
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from issuer.models import Issuer, BadgeClass, BadgeInstance, BadgeClassExtension
from mainsite.models import BadgrApp

User = get_user_model()


class UserCountInTopInstitutionsTest(TestCase):
    """
    Integration test for userCount field in topInstitutions.
    """

    def setUp(self):
        """Set up test fixtures"""
        # Create BadgrApp
        self.badgr_app = BadgrApp.objects.create(
            cors='testserver',
            name='Test App'
        )

        # Create authenticated user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )

        # Create test institution
        self.issuer = Issuer.objects.create(
            name="Test Institution",
            created_by=self.user
        )

        # Create learner users
        self.learner1 = User.objects.create_user(
            username='learner1',
            email='learner1@example.com',
            password='testpass'
        )
        self.learner2 = User.objects.create_user(
            username='learner2',
            email='learner2@example.com',
            password='testpass'
        )
        self.learner3 = User.objects.create_user(
            username='learner3',
            email='learner3@example.com',
            password='testpass'
        )

        # Create badge class with competency
        self.badge_class = BadgeClass.objects.create(
            name="Test Badge",
            description="Test Badge Description",
            issuer=self.issuer,
            created_by=self.user
        )

        # Add competency extension
        BadgeClassExtension.objects.create(
            badgeclass=self.badge_class,
            name='extensions:CompetencyExtension',
            original_json=[{
                'name': 'wissenschaftliche Daten analysieren',
                'studyLoad': 120,
                'description': 'Test competency'
            }]
        )

        # Create badge instances for different users
        # Learner1 gets 2 badges
        BadgeInstance.objects.create(
            badgeclass=self.badge_class,
            user=self.learner1,
            issuer=self.issuer
        )
        BadgeInstance.objects.create(
            badgeclass=self.badge_class,
            user=self.learner1,
            issuer=self.issuer
        )

        # Learner2 gets 1 badge
        BadgeInstance.objects.create(
            badgeclass=self.badge_class,
            user=self.learner2,
            issuer=self.issuer
        )

        # Learner3 gets 1 badge
        BadgeInstance.objects.create(
            badgeclass=self.badge_class,
            user=self.learner3,
            issuer=self.issuer
        )

        # Total: 4 badge instances, 3 unique users

        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_usercount_in_topinstitutions_response(self):
        """Test that userCount is present in topInstitutions"""
        url = reverse(
            'v1_api_competency_area_detail',
            kwargs={'area_id': 'wissenschaftliche_daten_analysieren'}
        )

        response = self.client.get(url)

        # Verify response status
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200, got {response.status_code}: {response.data}"
        )

        # Verify topInstitutions exists
        self.assertIn('topInstitutions', response.data)
        self.assertGreater(len(response.data['topInstitutions']), 0)

        # Verify userCount field exists
        institution = response.data['topInstitutions'][0]
        self.assertIn('userCount', institution,
                     f"userCount missing in topInstitutions. Got: {institution}")

    def test_usercount_reflects_unique_users(self):
        """Test that userCount shows unique users, not total badge count"""
        url = reverse(
            'v1_api_competency_area_detail',
            kwargs={'area_id': 'wissenschaftliche_daten_analysieren'}
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        institution = response.data['topInstitutions'][0]

        # Should have 3 unique users (learner1, learner2, learner3)
        self.assertEqual(
            institution['userCount'],
            3,
            f"Expected 3 unique users, got {institution['userCount']}"
        )

        # Should have 4 total badge instances
        self.assertEqual(
            institution['badgeCount'],
            4,
            f"Expected 4 badge instances, got {institution['badgeCount']}"
        )

    def test_statistics_totalusers_matches(self):
        """Test that statistics.totalUsers reflects the unique user count"""
        url = reverse(
            'v1_api_competency_area_detail',
            kwargs={'area_id': 'wissenschaftliche_daten_analysieren'}
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify statistics.totalUsers
        self.assertIn('statistics', response.data)
        self.assertEqual(
            response.data['statistics']['totalUsers'],
            3,
            f"Expected 3 total users, got {response.data['statistics']['totalUsers']}"
        )

        # Verify it matches topInstitutions[0].userCount
        institution = response.data['topInstitutions'][0]
        self.assertEqual(
            response.data['statistics']['totalUsers'],
            institution['userCount'],
            "statistics.totalUsers should match topInstitutions[0].userCount"
        )

    def test_multiple_institutions_usercount(self):
        """Test userCount with multiple institutions"""
        # Create second institution
        issuer2 = Issuer.objects.create(
            name="Second Institution",
            created_by=self.user
        )

        badge_class2 = BadgeClass.objects.create(
            name="Second Badge",
            description="Second Badge Description",
            issuer=issuer2,
            created_by=self.user
        )

        # Add same competency
        BadgeClassExtension.objects.create(
            badgeclass=badge_class2,
            name='extensions:CompetencyExtension',
            original_json=[{
                'name': 'wissenschaftliche Daten analysieren',
                'studyLoad': 120,
                'description': 'Test competency'
            }]
        )

        # Learner1 gets badge from second institution
        BadgeInstance.objects.create(
            badgeclass=badge_class2,
            user=self.learner1,
            issuer=issuer2
        )

        # Create new learner for second institution
        learner4 = User.objects.create_user(
            username='learner4',
            email='learner4@example.com',
            password='testpass'
        )
        BadgeInstance.objects.create(
            badgeclass=badge_class2,
            user=learner4,
            issuer=issuer2
        )

        url = reverse(
            'v1_api_competency_area_detail',
            kwargs={'area_id': 'wissenschaftliche_daten_analysieren'}
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find both institutions in response
        institutions = {
            inst['institutionName']: inst
            for inst in response.data['topInstitutions']
        }

        # First institution should have 3 unique users
        self.assertEqual(
            institutions['Test Institution']['userCount'],
            3,
            "Test Institution should have 3 unique users"
        )

        # Second institution should have 2 unique users (learner1 and learner4)
        self.assertEqual(
            institutions['Second Institution']['userCount'],
            2,
            "Second Institution should have 2 unique users"
        )

        # Total users should be 4 (learner1, 2, 3, 4)
        self.assertEqual(
            response.data['statistics']['totalUsers'],
            4,
            "Total unique users across all institutions should be 4"
        )
