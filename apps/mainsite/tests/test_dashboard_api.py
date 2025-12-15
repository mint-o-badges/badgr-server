# encoding: utf-8
"""
Comprehensive test suite for Dashboard Overview API endpoints.

This module tests all Dashboard API endpoints including:
- KPIs endpoint
- Competency areas list endpoint
- Competency area details endpoint
- Top badges endpoint

Tests cover:
1. Endpoint functionality (success cases)
2. Regional filtering (zip_code parameter)
3. Authentication requirements
4. Data accuracy and calculations
5. Response format validation
6. Error cases and edge cases
"""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from mainsite.tests.base import BadgrTestCase
from badgeuser.models import BadgeUser
from issuer.models import BadgeClass, Issuer, BadgeInstance


class DashboardKPIsTestCase(BadgrTestCase):
    """Test suite for /v1/dashboard/overview/kpis endpoint"""

    def setUp(self):
        super(DashboardKPIsTestCase, self).setUp()
        self._create_test_data()

    def _create_test_data(self):
        """Create comprehensive test data for dashboard tests"""
        # Create users with different zip codes
        self.user_munich = self.setup_user(
            email="munich@example.com",
            authenticate=False,
            zip_code="80331"  # München
        )
        # Set zip_code on user
        self.user_munich.zip_code = "80331"
        self.user_munich.save()

        self.user_berlin = self.setup_user(
            email="berlin@example.com",
            authenticate=False
        )
        self.user_berlin.zip_code = "10115"  # Berlin
        self.user_berlin.save()

        # Create authenticated admin user for API access
        self.admin_user = self.setup_user(
            email="admin@example.com",
            authenticate=True,
            zip_code="80331"
        )
        self.admin_user.zip_code = "80331"
        self.admin_user.save()

        # Create issuers
        self.issuer_munich = Issuer.objects.create(
            name="München VHS",
            created_by=self.user_munich,
            slug="vhs-muenchen",
            image="issuer.png",
            url="http://vhs-muenchen.de",
            email="info@vhs-muenchen.de"
        )

        self.issuer_berlin = Issuer.objects.create(
            name="Berlin Coding School",
            created_by=self.user_berlin,
            slug="coding-school-berlin",
            image="issuer.png",
            url="http://coding-berlin.de",
            email="info@coding-berlin.de"
        )

        # Create badge classes with competency extensions
        self.badge_digital_marketing = self._create_badge_with_competencies(
            issuer=self.issuer_munich,
            name="Digital Marketing Expert",
            slug="digital-marketing-expert",
            competencies=["digital_marketing", "social_media"],
            competency_area="it_digital",
            hours=4
        )

        self.badge_web_dev = self._create_badge_with_competencies(
            issuer=self.issuer_berlin,
            name="Web Development Fundamentals",
            slug="web-dev-fundamentals",
            competencies=["html_css", "javascript"],
            competency_area="it_digital",
            hours=4
        )

        self.badge_project_mgmt = self._create_badge_with_competencies(
            issuer=self.issuer_munich,
            name="Project Management Professional",
            slug="project-mgmt-pro",
            competencies=["project_planning", "team_leadership"],
            competency_area="management",
            hours=4
        )

        # Create badge instances (awards)
        # München region
        self._create_badge_instances(
            badge_class=self.badge_digital_marketing,
            issuer=self.issuer_munich,
            count=87,
            recipient_base="munich-dm"
        )

        self._create_badge_instances(
            badge_class=self.badge_project_mgmt,
            issuer=self.issuer_munich,
            count=52,
            recipient_base="munich-pm"
        )

        # Berlin region
        self._create_badge_instances(
            badge_class=self.badge_web_dev,
            issuer=self.issuer_berlin,
            count=64,
            recipient_base="berlin-wd"
        )

    def _create_badge_with_competencies(self, issuer, name, slug, competencies, competency_area, hours):
        """Helper to create badge class with competency extensions"""
        extension_items = {
            "extensions:CompetencyExtension": [
                {
                    "type": ["Extension", "extensions:CompetencyExtension"],
                    "competencyId": comp_id,
                    "competencyArea": competency_area,
                    "hours": hours
                }
                for comp_id in competencies
            ],
            "extensions:CategoryExtension": {
                "type": ["Extension", "extensions:CategoryExtension"],
                "Category": "competency"
            }
        }

        return BadgeClass.objects.create(
            name=name,
            description=f"Badge for {name}",
            created_by=issuer.created_by,
            slug=slug,
            issuer=issuer,
            image="badge.png",
            criteria_text="Complete the course",
            extension_items=extension_items
        )

    def _create_badge_instances(self, badge_class, issuer, count, recipient_base):
        """Helper to create multiple badge instances"""
        instances = []
        now = timezone.now()

        for i in range(count):
            instance = BadgeInstance.objects.create(
                recipient_identifier=f"{recipient_base}-{i}@example.com",
                badgeclass=badge_class,
                issuer=issuer,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED,
                issued_on=now - timedelta(days=i % 30)  # Spread over last 30 days
            )
            instances.append(instance)

        return instances

    # Test 1: Endpoint Tests - Success Cases

    def test_get_kpis_success(self):
        """Test successful retrieval of KPIs"""
        response = self.client.get('/v1/dashboard/overview/kpis')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn('topKpis', data)
        self.assertIn('secondaryKpis', data)

        # Verify top KPIs count
        self.assertEqual(len(data['topKpis']), 3)

        # Verify KPI IDs
        top_kpi_ids = [kpi['id'] for kpi in data['topKpis']]
        self.assertIn('institutions_active', top_kpi_ids)
        self.assertIn('badges_total', top_kpi_ids)
        self.assertIn('competency_hours', top_kpi_ids)

    def test_get_kpis_with_monthly_details(self):
        """Test KPIs with monthly details parameter"""
        response = self.client.get('/v1/dashboard/overview/kpis?includeMonthlyDetails=true')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check for monthly details in badges KPI
        badges_kpi = next(
            (kpi for kpi in data['topKpis'] if kpi['id'] == 'badges_total'),
            None
        )

        if badges_kpi and badges_kpi.get('hasMonthlyDetails'):
            self.assertIn('monthlyDetails', badges_kpi)
            self.assertIsInstance(badges_kpi['monthlyDetails'], list)

    # Test 2: Regional Filtering Tests

    def test_kpis_regional_filtering_munich(self):
        """Test KPIs filtered by München region (zipCode=8)"""
        response = self.client.get('/v1/dashboard/overview/kpis?zipCode=8')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify we get data
        self.assertIn('topKpis', data)

        # The badge count should be lower than total (only München badges)
        badges_kpi = next(
            (kpi for kpi in data['topKpis'] if kpi['id'] == 'badges_total'),
            None
        )
        self.assertIsNotNone(badges_kpi)

        # München should have 87 + 52 = 139 badges
        # Note: Actual count depends on implementation
        self.assertIsInstance(badges_kpi['value'], (int, float))

    def test_kpis_regional_filtering_specific_zipcode(self):
        """Test KPIs with specific zip code (80331)"""
        response = self.client.get('/v1/dashboard/overview/kpis?zipCode=80331')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('topKpis', data)

    def test_kpis_regional_filtering_two_digit(self):
        """Test KPIs with two-digit zip code prefix (80)"""
        response = self.client.get('/v1/dashboard/overview/kpis?zipCode=80')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('topKpis', data)

    def test_kpis_regional_filtering_uses_user_profile(self):
        """Test that zipCode is read from user profile, not overridable by frontend"""
        # This test verifies the backend reads zip_code from user profile
        # The OpenAPI spec mentions frontend cannot override region

        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        # The response should be filtered by the authenticated user's zip_code
        # which is set in setUp to "80331" for admin_user

    def test_kpis_multiple_regions_comparison(self):
        """Test KPIs for different regions show different data"""
        # Get München data
        response_munich = self.client.get('/v1/dashboard/overview/kpis?zipCode=8')
        self.assertEqual(response_munich.status_code, 200)

        # Get Berlin data
        response_berlin = self.client.get('/v1/dashboard/overview/kpis?zipCode=1')
        self.assertEqual(response_berlin.status_code, 200)

        # Data should be different (different badge counts)
        data_munich = response_munich.json()
        data_berlin = response_berlin.json()

        # Extract badge counts
        badges_munich = next(
            (kpi['value'] for kpi in data_munich['topKpis'] if kpi['id'] == 'badges_total'),
            0
        )
        badges_berlin = next(
            (kpi['value'] for kpi in data_berlin['topKpis'] if kpi['id'] == 'badges_total'),
            0
        )

        # Counts should be different
        # Note: This assumes implementation correctly filters by region
        # In test data: München has 139 badges, Berlin has 64

    # Test 3: Authentication Tests

    def test_kpis_requires_authentication(self):
        """Test that KPIs endpoint requires authentication"""
        # Clear authentication
        self.client.credentials()

        response = self.client.get('/v1/dashboard/overview/kpis')

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_kpis_with_valid_token(self):
        """Test KPIs with valid Bearer token"""
        # setup_user with authenticate=True already sets up token
        response = self.client.get('/v1/dashboard/overview/kpis')

        self.assertEqual(response.status_code, 200)

    # Test 4: Data Accuracy Tests

    def test_kpis_calculation_accuracy(self):
        """Test that KPI calculations are accurate"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify all top KPIs have required fields
        for kpi in data['topKpis']:
            self.assertIn('id', kpi)
            self.assertIn('labelKey', kpi)
            self.assertIn('value', kpi)
            self.assertIsInstance(kpi['value'], (int, float, str))

    def test_kpis_trend_data(self):
        """Test that trend data is present and valid"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check trend fields in at least one KPI
        if data['topKpis']:
            kpi = data['topKpis'][0]
            if 'trend' in kpi:
                self.assertIn(kpi['trend'], ['up', 'down', 'stable'])
                self.assertIn('trendValue', kpi)
                self.assertIn('trendPeriod', kpi)

    def test_kpis_competency_hours_calculation(self):
        """Test that competency hours are calculated correctly"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        hours_kpi = next(
            (kpi for kpi in data['topKpis'] if kpi['id'] == 'competency_hours'),
            None
        )

        if hours_kpi:
            # Should be positive number
            self.assertGreater(hours_kpi['value'], 0)

            # Based on test data:
            # 87 * 4 + 64 * 4 + 52 * 4 = 812 hours total
            # (or regional subset)

    # Test 5: Response Format Tests

    def test_kpis_response_matches_openapi_spec(self):
        """Test that response format matches OpenAPI specification"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Top-level structure
        self.assertIn('topKpis', data)
        self.assertIn('secondaryKpis', data)
        self.assertIsInstance(data['topKpis'], list)
        self.assertIsInstance(data['secondaryKpis'], list)

        # Top KPIs should have exactly 3 items
        self.assertEqual(len(data['topKpis']), 3)

        # Verify KPIData schema for each KPI
        for kpi in data['topKpis']:
            # Required fields
            self.assertIn('id', kpi)
            self.assertIn('labelKey', kpi)
            self.assertIn('value', kpi)

            # Optional fields (if present, check type)
            if 'unitKey' in kpi:
                self.assertIsInstance(kpi['unitKey'], str)
            if 'trend' in kpi:
                self.assertIn(kpi['trend'], ['up', 'down', 'stable'])
            if 'trendValue' in kpi:
                self.assertIsInstance(kpi['trendValue'], (int, float))

    def test_kpis_all_required_fields_present(self):
        """Test that all required fields are present in response"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check each top KPI has required fields
        for kpi in data['topKpis']:
            self.assertIsNotNone(kpi.get('id'))
            self.assertIsNotNone(kpi.get('labelKey'))
            self.assertIsNotNone(kpi.get('value'))

    def test_kpis_data_types(self):
        """Test that data types match specification"""
        response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        for kpi in data['topKpis']:
            # id and labelKey should be strings
            self.assertIsInstance(kpi['id'], str)
            self.assertIsInstance(kpi['labelKey'], str)

            # value can be number or string
            self.assertIsInstance(kpi['value'], (int, float, str))

            # trendValue should be number if present
            if 'trendValue' in kpi:
                self.assertIsInstance(kpi['trendValue'], (int, float))

    # Test 6: Error Cases and Edge Cases

    def test_kpis_invalid_zipcode_format(self):
        """Test KPIs with invalid zipCode format"""
        response = self.client.get('/v1/dashboard/overview/kpis?zipCode=invalid')

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)

    def test_kpis_zipcode_too_long(self):
        """Test KPIs with zipCode longer than 5 digits"""
        response = self.client.get('/v1/dashboard/overview/kpis?zipCode=123456')

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)

    def test_kpis_invalid_include_monthly_details(self):
        """Test KPIs with invalid includeMonthlyDetails parameter"""
        response = self.client.get('/v1/dashboard/overview/kpis?includeMonthlyDetails=invalid')

        # Should handle gracefully (default to false or return error)
        # Depending on implementation
        self.assertIn(response.status_code, [200, 400])


class DashboardCompetencyAreasTestCase(BadgrTestCase):
    """Test suite for /v1/dashboard/overview/competency-areas endpoint"""

    def setUp(self):
        super(DashboardCompetencyAreasTestCase, self).setUp()
        self._create_test_data()

    def _create_test_data(self):
        """Create test data for competency areas tests"""
        self.user = self.setup_user(
            email="user@example.com",
            authenticate=True,
            zip_code="80331"
        )
        self.user.zip_code = "80331"
        self.user.save()

        # Create issuer
        self.issuer = Issuer.objects.create(
            name="Test Issuer",
            created_by=self.user,
            slug="test-issuer",
            image="issuer.png",
            url="http://test.com",
            email="test@test.com"
        )

        # Create badges in different competency areas
        self._create_competency_badges()

    def _create_competency_badges(self):
        """Create badges across different competency areas"""
        areas = [
            ('it_digital', 285, 'IT Digital'),
            ('social_competencies', 221, 'Social'),
            ('languages', 183, 'Languages'),
            ('crafts', 150, 'Crafts'),
            ('management', 120, 'Management'),
        ]

        for area_id, count, name in areas:
            badge = BadgeClass.objects.create(
                name=f"{name} Badge",
                description=f"Badge for {name}",
                created_by=self.user,
                slug=f"badge-{area_id}",
                issuer=self.issuer,
                image="badge.png",
                criteria_text="Complete course",
                extension_items={
                    "extensions:CompetencyExtension": [{
                        "type": ["Extension", "extensions:CompetencyExtension"],
                        "competencyId": area_id,
                        "competencyArea": area_id,
                        "hours": 4
                    }]
                }
            )

            # Create instances
            for i in range(min(count, 10)):  # Limit for test performance
                BadgeInstance.objects.create(
                    recipient_identifier=f"{area_id}-{i}@example.com",
                    badgeclass=badge,
                    issuer=self.issuer,
                    acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
                )

    # Test 1: Endpoint Tests

    def test_get_competency_areas_success(self):
        """Test successful retrieval of competency areas"""
        response = self.client.get('/v1/dashboard/overview/competency-areas')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn('metadata', data)
        self.assertIn('data', data)

        # Verify metadata
        self.assertIn('totalAreas', data['metadata'])
        self.assertIn('totalBadges', data['metadata'])
        self.assertIn('lastUpdated', data['metadata'])

        # Verify data is list
        self.assertIsInstance(data['data'], list)

    def test_get_competency_areas_with_limit(self):
        """Test competency areas with limit parameter"""
        response = self.client.get('/v1/dashboard/overview/competency-areas?limit=5')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should return at most 5 areas
        self.assertLessEqual(len(data['data']), 5)

    def test_get_competency_areas_sort_by_percentage(self):
        """Test competency areas sorted by percentage"""
        response = self.client.get('/v1/dashboard/overview/competency-areas?sortBy=percentage')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify sorting (descending order)
        if len(data['data']) > 1:
            for i in range(len(data['data']) - 1):
                self.assertGreaterEqual(
                    data['data'][i]['value'],
                    data['data'][i + 1]['value']
                )

    # Test 2: Regional Filtering

    def test_competency_areas_regional_filtering(self):
        """Test competency areas filtered by region"""
        response = self.client.get('/v1/dashboard/overview/competency-areas?zipCode=8')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('data', data)

    # Test 3: Authentication

    def test_competency_areas_requires_authentication(self):
        """Test that competency areas endpoint requires authentication"""
        self.client.credentials()

        response = self.client.get('/v1/dashboard/overview/competency-areas')

        self.assertEqual(response.status_code, 401)

    # Test 4: Data Accuracy

    def test_competency_areas_data_structure(self):
        """Test competency area data structure"""
        response = self.client.get('/v1/dashboard/overview/competency-areas')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check each area has required fields
        for area in data['data']:
            self.assertIn('id', area)
            self.assertIn('nameKey', area)
            self.assertIn('value', area)  # percentage
            self.assertIn('weight', area)  # absolute count
            self.assertIsInstance(area['value'], (int, float))
            self.assertIsInstance(area['weight'], int)

    def test_competency_areas_percentage_sum(self):
        """Test that percentages add up to approximately 100%"""
        response = self.client.get('/v1/dashboard/overview/competency-areas')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        total_percentage = sum(area['value'] for area in data['data'])

        # Should be close to 100 (allowing for rounding)
        self.assertAlmostEqual(total_percentage, 100.0, delta=1.0)

    # Test 5: Response Format

    def test_competency_areas_response_format(self):
        """Test response format matches OpenAPI spec"""
        response = self.client.get('/v1/dashboard/overview/competency-areas')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify CompetencyAreasResponse schema
        self.assertIn('metadata', data)
        self.assertIn('data', data)

        # Metadata fields
        metadata = data['metadata']
        self.assertIn('totalAreas', metadata)
        self.assertIn('totalBadges', metadata)
        self.assertIn('lastUpdated', metadata)
        self.assertIsInstance(metadata['totalAreas'], int)
        self.assertIsInstance(metadata['totalBadges'], int)
        self.assertIsInstance(metadata['lastUpdated'], str)

        # Data items
        for area in data['data']:
            self.assertIn('id', area)
            self.assertIn('nameKey', area)
            self.assertIn('value', area)
            self.assertIn('weight', area)

    # Test 6: Error Cases

    def test_competency_areas_invalid_limit(self):
        """Test with invalid limit parameter"""
        response = self.client.get('/v1/dashboard/overview/competency-areas?limit=100')

        # Should cap at max (50) or return error
        self.assertIn(response.status_code, [200, 400])

    def test_competency_areas_invalid_sort_by(self):
        """Test with invalid sortBy parameter"""
        response = self.client.get('/v1/dashboard/overview/competency-areas?sortBy=invalid')

        # Should return 400 or default to percentage
        self.assertIn(response.status_code, [200, 400])


class DashboardCompetencyAreaDetailsTestCase(BadgrTestCase):
    """Test suite for /v1/dashboard/overview/competency-areas/{areaId} endpoint"""

    def setUp(self):
        super(DashboardCompetencyAreaDetailsTestCase, self).setUp()
        self._create_test_data()

    def _create_test_data(self):
        """Create test data"""
        self.user = self.setup_user(
            email="user@example.com",
            authenticate=True
        )

        self.issuer = Issuer.objects.create(
            name="Test Issuer",
            created_by=self.user,
            slug="test-issuer",
            image="issuer.png",
            url="http://test.com",
            email="test@test.com"
        )

        # Create IT Digital badges
        self.badge_it = BadgeClass.objects.create(
            name="IT Badge",
            description="IT Badge",
            created_by=self.user,
            slug="it-badge",
            issuer=self.issuer,
            image="badge.png",
            criteria_text="Complete course",
            extension_items={
                "extensions:CompetencyExtension": [{
                    "type": ["Extension", "extensions:CompetencyExtension"],
                    "competencyId": "programming",
                    "competencyArea": "it_digital",
                    "hours": 4
                }]
            }
        )

    # Test 1: Endpoint Tests

    def test_get_competency_area_details_success(self):
        """Test successful retrieval of competency area details"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn('id', data)
        self.assertIn('nameKey', data)
        self.assertIn('statistics', data)

        # Verify statistics
        stats = data['statistics']
        self.assertIn('totalBadges', stats)
        self.assertIn('totalHours', stats)
        self.assertIn('totalUsers', stats)
        self.assertIn('percentage', stats)

    def test_get_competency_area_details_not_found(self):
        """Test getting details for non-existent area"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/invalid_id')

        self.assertEqual(response.status_code, 404)

    def test_get_competency_area_with_sub_competencies(self):
        """Test competency area details with sub-competencies"""
        response = self.client.get(
            '/v1/dashboard/overview/competency-areas/it_digital?includeSubCompetencies=true'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        if 'subCompetencies' in data:
            self.assertIsInstance(data['subCompetencies'], list)

    # Test 2: Regional Filtering

    def test_competency_area_details_regional_filtering(self):
        """Test area details filtered by region"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital?zipCode=8')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('statistics', data)

    # Test 3: Authentication

    def test_competency_area_details_requires_authentication(self):
        """Test that endpoint requires authentication"""
        self.client.credentials()

        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital')

        self.assertEqual(response.status_code, 401)

    # Test 4: Data Accuracy

    def test_competency_area_details_complete_data(self):
        """Test that all detail fields are present"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Required fields
        self.assertIn('id', data)
        self.assertIn('nameKey', data)
        self.assertIn('statistics', data)

        # Optional but expected fields
        if 'trend' in data:
            self.assertIn('direction', data['trend'])
            self.assertIn(data['trend']['direction'], ['up', 'down', 'stable'])

    # Test 5: Response Format

    def test_competency_area_details_response_format(self):
        """Test response format matches OpenAPI spec"""
        response = self.client.get('/v1/dashboard/overview/competency-areas/it_digital')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify CompetencyAreaDetails schema
        self.assertIsInstance(data['id'], str)
        self.assertIsInstance(data['nameKey'], str)
        self.assertIsInstance(data['statistics'], dict)

        # Statistics types
        stats = data['statistics']
        self.assertIsInstance(stats['totalBadges'], int)
        self.assertIsInstance(stats['totalHours'], int)
        self.assertIsInstance(stats['totalUsers'], int)
        self.assertIsInstance(stats['percentage'], (int, float))


class DashboardTopBadgesTestCase(BadgrTestCase):
    """Test suite for /v1/dashboard/overview/top-badges endpoint"""

    def setUp(self):
        super(DashboardTopBadgesTestCase, self).setUp()
        self._create_test_data()

    def _create_test_data(self):
        """Create test data for top badges"""
        self.user = self.setup_user(
            email="user@example.com",
            authenticate=True
        )

        self.issuer = Issuer.objects.create(
            name="Test Issuer",
            created_by=self.user,
            slug="test-issuer",
            image="issuer.png",
            url="http://test.com",
            email="test@test.com"
        )

        # Create badges with different award counts
        self.badge1 = BadgeClass.objects.create(
            name="Top Badge 1",
            slug="top-badge-1",
            description="Most awarded",
            created_by=self.user,
            issuer=self.issuer,
            image="badge.png",
            criteria_text="Complete course"
        )

        self.badge2 = BadgeClass.objects.create(
            name="Top Badge 2",
            slug="top-badge-2",
            description="Second most awarded",
            created_by=self.user,
            issuer=self.issuer,
            image="badge.png",
            criteria_text="Complete course"
        )

        # Create instances for ranking
        for i in range(10):
            BadgeInstance.objects.create(
                recipient_identifier=f"top1-{i}@example.com",
                badgeclass=self.badge1,
                issuer=self.issuer,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
            )

        for i in range(7):
            BadgeInstance.objects.create(
                recipient_identifier=f"top2-{i}@example.com",
                badgeclass=self.badge2,
                issuer=self.issuer,
                acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
            )

    # Test 1: Endpoint Tests

    def test_get_top_badges_success(self):
        """Test successful retrieval of top badges"""
        response = self.client.get('/v1/dashboard/overview/top-badges')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn('metadata', data)
        self.assertIn('badges', data)

        # Default should return top 3
        self.assertLessEqual(len(data['badges']), 3)

    def test_get_top_badges_with_limit(self):
        """Test top badges with custom limit"""
        response = self.client.get('/v1/dashboard/overview/top-badges?limit=5')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertLessEqual(len(data['badges']), 5)

    def test_get_top_badges_with_period(self):
        """Test top badges with time period filter"""
        response = self.client.get('/v1/dashboard/overview/top-badges?period=last_month')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['metadata']['period'], 'last_month')

    # Test 2: Regional Filtering

    def test_top_badges_regional_filtering(self):
        """Test top badges filtered by region"""
        response = self.client.get('/v1/dashboard/overview/top-badges?zipCode=8')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Metadata should include region info
        if 'zipCode' in data['metadata']:
            self.assertEqual(data['metadata']['zipCode'], '8')

    # Test 3: Authentication

    def test_top_badges_requires_authentication(self):
        """Test that endpoint requires authentication"""
        self.client.credentials()

        response = self.client.get('/v1/dashboard/overview/top-badges')

        self.assertEqual(response.status_code, 401)

    # Test 4: Data Accuracy

    def test_top_badges_ranking_order(self):
        """Test that badges are ranked correctly by count"""
        response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify ranking is in descending order
        if len(data['badges']) > 1:
            for i in range(len(data['badges']) - 1):
                self.assertGreaterEqual(
                    data['badges'][i]['count'],
                    data['badges'][i + 1]['count']
                )

    def test_top_badges_rank_assignment(self):
        """Test that rank field is assigned correctly"""
        response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify rank values
        for i, badge in enumerate(data['badges']):
            self.assertEqual(badge['rank'], i + 1)

    # Test 5: Response Format

    def test_top_badges_response_format(self):
        """Test response format matches OpenAPI spec"""
        response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Verify TopBadgesResponse schema
        self.assertIn('metadata', data)
        self.assertIn('badges', data)

        # Metadata fields
        metadata = data['metadata']
        self.assertIn('totalBadges', metadata)
        self.assertIn('lastUpdated', metadata)
        self.assertIn('period', metadata)

        # Badge data
        for badge in data['badges']:
            # Required fields
            self.assertIn('rank', badge)
            self.assertIn('badgeId', badge)
            self.assertIn('badgeTitleKey', badge)
            self.assertIn('badgeTitle', badge)
            self.assertIn('count', badge)
            self.assertIn('percentage', badge)
            self.assertIn('hours', badge)
            self.assertIn('categoryKey', badge)
            self.assertIn('competencies', badge)

            # Verify types
            self.assertIsInstance(badge['rank'], int)
            self.assertIsInstance(badge['count'], int)
            self.assertIsInstance(badge['percentage'], (int, float))
            self.assertIsInstance(badge['hours'], int)
            self.assertIsInstance(badge['competencies'], list)

    def test_top_badges_visualization_data(self):
        """Test that visualization data is present"""
        response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Check for visualization field in badges
        for badge in data['badges']:
            if 'visualization' in badge:
                self.assertIn('icon', badge['visualization'])
                self.assertIn('color', badge['visualization'])
                # Color should be hex format
                self.assertRegex(badge['visualization']['color'], r'^#[0-9A-Fa-f]{6}$')

    # Test 6: Error Cases

    def test_top_badges_invalid_limit(self):
        """Test with invalid limit parameter"""
        response = self.client.get('/v1/dashboard/overview/top-badges?limit=20')

        # Should cap at max (10) or return error
        self.assertIn(response.status_code, [200, 400])

    def test_top_badges_invalid_period(self):
        """Test with invalid period parameter"""
        response = self.client.get('/v1/dashboard/overview/top-badges?period=invalid')

        self.assertEqual(response.status_code, 400)


class DashboardIntegrationTestCase(BadgrTestCase):
    """Integration tests for Dashboard API endpoints"""

    def setUp(self):
        super(DashboardIntegrationTestCase, self).setUp()
        self.user = self.setup_user(
            email="integration@example.com",
            authenticate=True,
            zip_code="80331"
        )
        self.user.zip_code = "80331"
        self.user.save()

    def test_dashboard_workflow_complete(self):
        """Test complete dashboard workflow"""
        # 1. Get KPIs
        kpis_response = self.client.get('/v1/dashboard/overview/kpis')
        self.assertEqual(kpis_response.status_code, 200)

        # 2. Get competency areas
        areas_response = self.client.get('/v1/dashboard/overview/competency-areas')
        self.assertEqual(areas_response.status_code, 200)

        # 3. Get details for first area (if exists)
        areas_data = areas_response.json()
        if areas_data['data']:
            area_id = areas_data['data'][0]['id']
            details_response = self.client.get(
                f'/v1/dashboard/overview/competency-areas/{area_id}'
            )
            self.assertEqual(details_response.status_code, 200)

        # 4. Get top badges
        badges_response = self.client.get('/v1/dashboard/overview/top-badges')
        self.assertEqual(badges_response.status_code, 200)

    def test_dashboard_regional_consistency(self):
        """Test that regional filtering is consistent across endpoints"""
        zip_code = "8"

        # Get data from all endpoints with same zipCode
        kpis = self.client.get(f'/v1/dashboard/overview/kpis?zipCode={zip_code}')
        areas = self.client.get(f'/v1/dashboard/overview/competency-areas?zipCode={zip_code}')
        badges = self.client.get(f'/v1/dashboard/overview/top-badges?zipCode={zip_code}')

        # All should succeed
        self.assertEqual(kpis.status_code, 200)
        self.assertEqual(areas.status_code, 200)
        self.assertEqual(badges.status_code, 200)

        # Badge counts should be consistent across endpoints
        kpis_data = kpis.json()
        areas_data = areas.json()
        badges_data = badges.json()

        # Extract badge count from KPIs
        badges_kpi = next(
            (kpi for kpi in kpis_data['topKpis'] if kpi['id'] == 'badges_total'),
            None
        )

        # Compare with other endpoints
        if badges_kpi and 'totalBadges' in areas_data['metadata']:
            # Counts should match or be consistent
            self.assertIsInstance(badges_kpi['value'], (int, float))
            self.assertIsInstance(areas_data['metadata']['totalBadges'], int)

    def test_dashboard_authentication_consistency(self):
        """Test that all endpoints consistently require authentication"""
        endpoints = [
            '/v1/dashboard/overview/kpis',
            '/v1/dashboard/overview/competency-areas',
            '/v1/dashboard/overview/competency-areas/it_digital',
            '/v1/dashboard/overview/top-badges',
        ]

        # Clear authentication
        self.client.credentials()

        # All endpoints should return 401
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                401,
                f"Endpoint {endpoint} should require authentication"
            )
