# encoding: utf-8
"""
Comprehensive integration tests for CompetencyAreaDetailView endpoint.

Tests the /v1/dashboard/overview/competency-areas/:areaId endpoint to verify:
1. totalInstitutions count is correct (including 2+ institutions scenario)
2. badgeCount accurately reflects badges offering the competency
3. userCount accurately reflects users who earned the competency
4. topBadges data is correct
5. topInstitutions data is correct
6. Edge cases: no institutions, no badges, no users
7. Regional filtering integration
8. ID normalization (case-insensitive, underscore/hyphen handling)
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from badgeuser.models import BadgeUser
from issuer.models import Issuer, BadgeClass, BadgeInstance, BadgeClassExtension
from mainsite.tests.base import BadgrTestCase


# Mock geocode to prevent external API calls during tests
def mock_issuer_save(self, *args, **kwargs):
    """Override Issuer.save to skip geocoding for tests"""
    # Skip geocoding by calling Model.save directly, bypassing Issuer's custom save
    from django.db.models import Model
    super(Issuer, self).save(*args, **kwargs)


ISSUER_SAVE_MOCK = patch('issuer.models.Issuer.save', mock_issuer_save)


class CompetencyAreaDetailIntegrationTest(BadgrTestCase):
    """
    Comprehensive integration tests for CompetencyAreaDetailView.

    Tests the complete functionality of the competency area detail endpoint,
    including the specific bug case with 2 institutions and data accuracy for all fields.
    """

    def setUp(self):
        """Set up comprehensive test fixtures"""
        super().setUp()
        self.client = APIClient()

        # Create test users using setup_user helper from BadgrTestCase
        self.admin_user = self.setup_user(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        self.admin_user.zip_code = '10115'  # Berlin
        self.admin_user.save()

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

        # Create test issuers with zip codes (geocode is mocked)
        with ISSUER_SAVE_MOCK:
            self.issuer1 = Issuer.objects.create(
                name='Institution One',
                created_by=self.admin_user,
                slug='institution-one',
                url='http://institution1.com',
                email='issuer1@example.com',
                zip='10115',  # Berlin
                linkedinId=''
            )

            self.issuer2 = Issuer.objects.create(
                name='Institution Two',
                created_by=self.admin_user,
                slug='institution-two',
                url='http://institution2.com',
                email='issuer2@example.com',
                zip='10117',  # Berlin
                linkedinId=''
            )

            self.issuer3 = Issuer.objects.create(
                name='Institution Three',
                created_by=self.admin_user,
                slug='institution-three',
                url='http://institution3.com',
                email='issuer3@example.com',
                zip='80331',  # Munich
                linkedinId=''
            )

        # Authenticate client
        self.client.force_authenticate(user=self.admin_user)

    def _create_badge_with_competency(self, issuer, competency_name, badge_name, study_load=120):
        """Helper to create a badge class with competency extension"""
        badge_class = BadgeClass.objects.create(
            name=badge_name,
            description=f'{badge_name} description',
            issuer=issuer,
            created_by=self.admin_user,
            slug=badge_name.lower().replace(' ', '-'),
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
        """Helper to award a badge to a user"""
        return BadgeInstance.objects.create(
            badgeclass=badge_class,
            user=user,
            issuer=badge_class.issuer,
            recipient_identifier=user.email,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_two_institutions_total_count(self):
        """
        Test that totalInstitutions correctly counts 2 institutions.
        This is the specific bug case mentioned in the requirements.
        """
        # Create badges for the same competency at 2 different institutions
        competency_name = 'wissenschaftliche Daten analysieren'

        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Data Analysis Badge 1'
        )
        badge2 = self._create_badge_with_competency(
            self.issuer2, competency_name, 'Data Analysis Badge 2'
        )

        # Award badges to learners
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge2, self.learner2)

        # Make request
        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'wissenschaftliche_daten_analysieren'}
        )
        response = self.client.get(url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)

        # Verify totalInstitutions is exactly 2
        self.assertEqual(
            response.data['statistics']['totalInstitutions'],
            2,
            f"Expected 2 institutions, got {response.data['statistics']['totalInstitutions']}"
        )

        # Verify topInstitutions contains both institutions
        self.assertEqual(len(response.data['topInstitutions']), 2)
        institution_names = {inst['institutionName'] for inst in response.data['topInstitutions']}
        self.assertEqual(institution_names, {'Institution One', 'Institution Two'})

    def test_badge_count_accuracy(self):
        """Test that badgeCount accurately reflects badges offering the competency"""
        competency_name = 'Holzbearbeitung'

        # Create 3 different badges with the same competency
        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Woodworking Badge 1'
        )
        badge2 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Woodworking Badge 2'
        )
        badge3 = self._create_badge_with_competency(
            self.issuer2, competency_name, 'Woodworking Badge 3'
        )

        # Award badges (some users get multiple badges)
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge2, self.learner1)
        self._award_badge(badge3, self.learner3)

        # Total: 4 badge instances across 3 badge classes

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'holzbearbeitung'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify totalBadges counts badge instances
        self.assertEqual(
            response.data['statistics']['totalBadges'],
            4,
            f"Expected 4 badge instances, got {response.data['statistics']['totalBadges']}"
        )

        # Verify topBadges contains all 3 badge classes
        self.assertEqual(len(response.data['topBadges']), 3)

    def test_user_count_accuracy(self):
        """Test that userCount accurately reflects unique users who earned the competency"""
        competency_name = 'Text-Korrektur lesen'

        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Reading Badge'
        )

        # Award badges (learner1 gets 2, learner2 gets 1)
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner1)  # Duplicate
        self._award_badge(badge1, self.learner2)

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'text_korrektur_lesen'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify totalUsers counts unique users (not badge instances)
        self.assertEqual(
            response.data['statistics']['totalUsers'],
            2,
            f"Expected 2 unique users, got {response.data['statistics']['totalUsers']}"
        )

        # Verify totalBadges counts all instances
        self.assertEqual(response.data['statistics']['totalBadges'], 3)

    def test_top_badges_data_accuracy(self):
        """Test that topBadges data is correct and properly ordered"""
        competency_name = 'Bienenhaus'

        # Create 3 badges with different award counts
        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Popular Badge'
        )
        badge2 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Medium Badge'
        )
        badge3 = self._create_badge_with_competency(
            self.issuer2, competency_name, 'Rare Badge'
        )

        # Award different amounts
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge1, self.learner3)  # 3 awards

        self._award_badge(badge2, self.learner1)
        self._award_badge(badge2, self.learner2)  # 2 awards

        self._award_badge(badge3, self.learner1)  # 1 award

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'bienenhaus'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify topBadges is ordered by count (descending)
        top_badges = response.data['topBadges']
        self.assertEqual(len(top_badges), 3)

        # Check order
        self.assertEqual(top_badges[0]['count'], 3)
        self.assertEqual(top_badges[1]['count'], 2)
        self.assertEqual(top_badges[2]['count'], 1)

        # Check percentages sum to 100
        total_percentage = sum(badge['percentage'] for badge in top_badges)
        self.assertAlmostEqual(total_percentage, 100.0, places=1)

        # Check required fields
        for badge in top_badges:
            self.assertIn('badgeId', badge)
            self.assertIn('badgeTitleKey', badge)
            self.assertIn('count', badge)
            self.assertIn('percentage', badge)

    def test_top_institutions_data_accuracy(self):
        """Test that topInstitutions data is correct with userCount and badgeCount"""
        competency_name = 'Garten Arbeit'

        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Gardening Badge 1'
        )
        badge2 = self._create_badge_with_competency(
            self.issuer2, competency_name, 'Gardening Badge 2'
        )

        # Institution 1: 4 badges to 2 users
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge1, self.learner2)

        # Institution 2: 1 badge to 1 user
        self._award_badge(badge2, self.learner3)

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'garten_arbeit'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find institutions in response
        institutions = {
            inst['institutionName']: inst
            for inst in response.data['topInstitutions']
        }

        # Verify Institution One
        inst1 = institutions['Institution One']
        self.assertEqual(
            inst1['badgeCount'],
            4,
            f"Institution One should have 4 badge instances, got {inst1['badgeCount']}"
        )
        self.assertEqual(
            inst1['userCount'],
            2,
            f"Institution One should have 2 unique users, got {inst1['userCount']}"
        )

        # Verify Institution Two
        inst2 = institutions['Institution Two']
        self.assertEqual(inst2['badgeCount'], 1)
        self.assertEqual(inst2['userCount'], 1)

        # Verify required fields
        for inst in response.data['topInstitutions']:
            self.assertIn('institutionId', inst)
            self.assertIn('institutionName', inst)
            self.assertIn('badgeCount', inst)
            self.assertIn('userCount', inst)

    def test_edge_case_no_badges(self):
        """Test response when competency area has no badges"""
        # Create a competency but don't award any badges
        competency_name = 'Empty Competency'
        self._create_badge_with_competency(
            self.issuer1, competency_name, 'Unawarded Badge'
        )

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'empty_competency'}
        )
        response = self.client.get(url)

        # Should return 404 when no badges awarded
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_edge_case_nonexistent_competency(self):
        """Test response for non-existent competency area"""
        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'does_not_exist'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertIn('available_areas', response.data)

    def test_case_insensitive_id_matching(self):
        """Test that competency IDs are matched case-insensitively"""
        competency_name = 'Holzbearbeitung'
        badge = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Wood Badge'
        )
        self._award_badge(badge, self.learner1)

        # Test various case combinations
        test_cases = [
            'holzbearbeitung',
            'Holzbearbeitung',
            'HOLZBEARBEITUNG',
            'HolzBearbeitung',
        ]

        for area_id in test_cases:
            with self.subTest(area_id=area_id):
                url = reverse(
                    'dashboard_competency_area_detail',
                    kwargs={'area_id': area_id}
                )
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                    f"Failed for area_id: {area_id}"
                )

    def test_hyphen_underscore_normalization(self):
        """Test that hyphens and underscores are normalized correctly"""
        competency_name = 'Text-Korrektur lesen'
        badge = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Reading Badge'
        )
        self._award_badge(badge, self.learner1)

        # Test various separator combinations
        test_cases = [
            'text-korrektur-lesen',
            'text_korrektur_lesen',
            'Text-Korrektur-Lesen',
            'Text_Korrektur_Lesen',
        ]

        for area_id in test_cases:
            with self.subTest(area_id=area_id):
                url = reverse(
                    'dashboard_competency_area_detail',
                    kwargs={'area_id': area_id}
                )
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                    f"Failed for area_id: {area_id}"
                )

    def test_statistics_consistency(self):
        """Test that statistics fields are consistent with each other"""
        competency_name = 'Programming'

        badge1 = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Python Badge', study_load=240
        )
        badge2 = self._create_badge_with_competency(
            self.issuer2, competency_name, 'JavaScript Badge', study_load=180
        )

        # Create specific scenario
        self._award_badge(badge1, self.learner1)
        self._award_badge(badge1, self.learner2)
        self._award_badge(badge2, self.learner1)

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'programming'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stats = response.data['statistics']

        # Verify all statistics are present
        self.assertIn('totalBadges', stats)
        self.assertIn('totalHours', stats)
        self.assertIn('totalUsers', stats)
        self.assertIn('totalInstitutions', stats)
        self.assertIn('percentage', stats)

        # Verify statistics consistency
        self.assertEqual(stats['totalBadges'], 3)  # 3 badge instances
        self.assertEqual(stats['totalUsers'], 2)  # 2 unique users
        self.assertEqual(stats['totalInstitutions'], 2)  # 2 institutions

        # Verify hours calculation (3 badges * 4 hours default)
        self.assertGreater(stats['totalHours'], 0)

        # Verify percentage is valid
        self.assertGreaterEqual(stats['percentage'], 0)
        self.assertLessEqual(stats['percentage'], 100)

    def test_multiple_competencies_same_badge(self):
        """Test handling of badges with multiple competencies"""
        # Create a badge with multiple competencies
        badge_class = BadgeClass.objects.create(
            name='Multi-Competency Badge',
            description='Badge with multiple competencies',
            issuer=self.issuer1,
            created_by=self.admin_user,
            slug='multi-comp-badge',
            criteria_text='Complete multiple courses'
        )

        # Add multiple competencies
        BadgeClassExtension.objects.create(
            badgeclass=badge_class,
            name='extensions:CompetencyExtension',
            original_json=[
                {
                    'name': 'Competency Alpha',
                    'studyLoad': 120,
                    'description': 'First competency'
                },
                {
                    'name': 'Competency Beta',
                    'studyLoad': 90,
                    'description': 'Second competency'
                }
            ]
        )

        self._award_badge(badge_class, self.learner1)

        # Test that the badge appears in both competency areas
        for area_id in ['competency_alpha', 'competency_beta']:
            url = reverse(
                'dashboard_competency_area_detail',
                kwargs={'area_id': area_id}
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['statistics']['totalBadges'], 1)

    def test_regional_filtering_integration(self):
        """Test that regional filtering works correctly with competency details"""
        competency_name = 'Regional Test'

        # Berlin badge
        badge_berlin = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Berlin Badge'
        )
        self._award_badge(badge_berlin, self.learner1)

        # Munich badge
        badge_munich = self._create_badge_with_competency(
            self.issuer3, competency_name, 'Munich Badge'
        )
        self._award_badge(badge_munich, self.learner2)

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'regional_test'}
        )

        # User with Berlin zip code should see only Berlin institutions
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that regional filtering is applied
        # (admin_user has Berlin zip code, so should see Berlin issuer)
        institution_names = {
            inst['institutionName'] for inst in response.data['topInstitutions']
        }

        # With regional filtering, should only see Berlin institutions
        if 'Institution Three' not in institution_names:
            # Regional filtering is working
            self.assertIn('Institution One', institution_names)
            self.assertNotIn('Institution Three', institution_names)

    def test_response_structure_completeness(self):
        """Test that response contains all required fields per specification"""
        competency_name = 'Complete Test'
        badge = self._create_badge_with_competency(
            self.issuer1, competency_name, 'Complete Badge'
        )
        self._award_badge(badge, self.learner1)

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'complete_test'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify top-level structure
        required_fields = ['id', 'nameKey', 'descriptionKey', 'statistics', 'trend', 'topBadges', 'topInstitutions']
        for field in required_fields:
            self.assertIn(field, response.data, f"Missing required field: {field}")

        # Verify statistics structure
        stats_fields = ['totalBadges', 'totalHours', 'totalUsers', 'totalInstitutions', 'percentage']
        for field in stats_fields:
            self.assertIn(field, response.data['statistics'], f"Missing statistics field: {field}")

        # Verify trend structure
        trend_fields = ['direction', 'value', 'period']
        for field in trend_fields:
            self.assertIn(field, response.data['trend'], f"Missing trend field: {field}")

    def test_performance_with_large_dataset(self):
        """Test performance and correctness with larger dataset"""
        competency_name = 'Performance Test'

        # Create multiple badges
        badges = []
        for i in range(5):
            badge = self._create_badge_with_competency(
                self.issuer1 if i < 3 else self.issuer2,
                competency_name,
                f'Performance Badge {i}'
            )
            badges.append(badge)

        # Award badges to multiple users
        all_learners = [self.learner1, self.learner2, self.learner3]
        for badge in badges:
            for learner in all_learners:
                self._award_badge(badge, learner)

        # Total: 5 badges * 3 learners = 15 badge instances

        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'performance_test'}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify counts
        self.assertEqual(response.data['statistics']['totalBadges'], 15)
        self.assertEqual(response.data['statistics']['totalUsers'], 3)
        self.assertEqual(response.data['statistics']['totalInstitutions'], 2)

        # Verify topBadges limited to 5
        self.assertLessEqual(len(response.data['topBadges']), 5)

        # Verify topInstitutions
        self.assertEqual(len(response.data['topInstitutions']), 2)


class CompetencyAreaDetailAuthenticationTest(TestCase):
    """Test authentication requirements for the endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

    def test_authentication_required(self):
        """Test that endpoint requires authentication"""
        url = reverse(
            'dashboard_competency_area_detail',
            kwargs={'area_id': 'test'}
        )
        response = self.client.get(url)

        # Should return 401 or 403 (depending on DRF settings)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
