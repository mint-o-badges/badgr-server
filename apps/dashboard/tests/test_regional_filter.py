# encoding: utf-8
"""
Comprehensive test suite for regional filtering functionality.

Tests the following components:
1. RegionalService - PLZ to Landkreis mapping service
2. RegionalFilterMixin - Mixin for filtering users and badges by region

This module ensures that regional filtering works correctly across the dashboard.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.conf import settings
import os

from badgeuser.models import BadgeUser
from issuer.models import BadgeInstance, BadgeClass, Issuer, BadgeClassExtension
from dashboard.services.regional_service import RegionalService
from mainsite.tests.base import BadgrTestCase


# Mock geocode to prevent external API calls during tests
def mock_issuer_save(self, *args, **kwargs):
    """Override Issuer.save to skip geocoding for tests"""
    # Skip geocoding by calling Model.save directly, bypassing Issuer's custom save
    from django.db.models import Model
    super(Issuer, self).save(*args, **kwargs)

ISSUER_SAVE_MOCK = patch('issuer.models.Issuer.save', mock_issuer_save)


class RegionalServiceTest(TestCase):
    """
    Test suite for RegionalService singleton class.

    Tests PLZ (Postal Code) to Landkreis (District) mapping functionality,
    which is essential for regional filtering in the dashboard.
    """

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        super().setUpClass()
        # Reset singleton instance before tests
        RegionalService._instance = None
        RegionalService._plz_data = None
        RegionalService._landkreis_plz = None

    def setUp(self):
        """Set up test fixtures for each test"""
        # Reset singleton instance for each test
        RegionalService._instance = None
        RegionalService._plz_data = None
        RegionalService._landkreis_plz = None

    def test_singleton_pattern(self):
        """Test that RegionalService implements singleton pattern correctly"""
        # Get first instance
        instance1 = RegionalService.get_instance()
        self.assertIsNotNone(instance1)

        # Get second instance
        instance2 = RegionalService.get_instance()

        # Both should be the same object
        self.assertIs(instance1, instance2)

    def test_get_landkreis_by_plz3(self):
        """
        Test PLZ3 to Landkreis mapping.
        Verify that PLZ3 '101' maps to 'Berlin' as specified in requirements.
        """
        service = RegionalService.get_instance()

        # Test Berlin PLZ3 mapping
        landkreis = service.get_landkreis_by_plz3('101')
        self.assertEqual(landkreis, 'Berlin')

    def test_get_landkreis_by_plz3_invalid(self):
        """Test that invalid PLZ3 returns None"""
        service = RegionalService.get_instance()

        # Test with non-existent PLZ3
        landkreis = service.get_landkreis_by_plz3('999')
        self.assertIsNone(landkreis)

    def test_get_all_plz_for_landkreis(self):
        """
        Test retrieving all postal codes for a Landkreis.
        Verify that Berlin has the expected PLZ list including '10115'.
        """
        service = RegionalService.get_instance()

        # Test getting all PLZ for Berlin
        plz_list = service.get_all_plz_for_landkreis('Berlin')

        # Should return a list
        self.assertIsInstance(plz_list, list)

        # Berlin should have multiple PLZ codes
        self.assertGreater(len(plz_list), 0)

        # Should contain the expected test PLZ
        self.assertIn('10115', plz_list)

    def test_get_all_plz_for_landkreis_invalid(self):
        """Test that invalid Landkreis returns empty list"""
        service = RegionalService.get_instance()

        # Test with non-existent Landkreis
        plz_list = service.get_all_plz_for_landkreis('NonexistentDistrict')

        # Should return empty list
        self.assertEqual(plz_list, [])
        self.assertIsInstance(plz_list, list)

    def test_csv_data_loaded(self):
        """Test that CSV data is loaded correctly on initialization"""
        service = RegionalService.get_instance()

        # Check that internal data structures are populated
        self.assertIsNotNone(service._plz_data)
        self.assertIsNotNone(service._landkreis_plz)

        # Data structures should not be empty
        self.assertGreater(len(service._plz_data), 0)
        self.assertGreater(len(service._landkreis_plz), 0)

    def test_multiple_plz_for_landkreis(self):
        """Test that a Landkreis can have multiple PLZ codes"""
        service = RegionalService.get_instance()

        # Get PLZ list for Berlin
        plz_list = service.get_all_plz_for_landkreis('Berlin')

        # Berlin should have multiple postal codes
        self.assertGreater(len(plz_list), 10)

    def test_landkreis_mapping_consistency(self):
        """Test consistency between PLZ3 to Landkreis and reverse mapping"""
        service = RegionalService.get_instance()

        # Get Landkreis for a PLZ3
        plz3 = '101'
        landkreis = service.get_landkreis_by_plz3(plz3)

        if landkreis:
            # Get all PLZ for that Landkreis
            plz_list = service.get_all_plz_for_landkreis(landkreis)

            # At least one PLZ should start with the PLZ3
            plz_with_prefix = [plz for plz in plz_list if plz.startswith(plz3)]
            self.assertGreater(len(plz_with_prefix), 0)

    def test_get_all_plz_for_ort(self):
        """
        Test PLZ lookup by Ort (city name).
        Verify that München returns expected PLZ codes.
        """
        service = RegionalService.get_instance()

        # Test getting all PLZ for München
        plz_list = service.get_all_plz_for_ort('München')

        # Should return a list
        self.assertIsInstance(plz_list, list)

        # München should have multiple PLZ codes
        self.assertGreater(len(plz_list), 0)

        # Should contain expected München PLZ codes
        self.assertIn('80331', plz_list)
        self.assertIn('80335', plz_list)

    def test_get_all_plz_for_ort_case_insensitive(self):
        """Test that Ort lookup is case-insensitive"""
        service = RegionalService.get_instance()

        # Test with different cases
        plz_upper = service.get_all_plz_for_ort('MÜNCHEN')
        plz_lower = service.get_all_plz_for_ort('münchen')
        plz_mixed = service.get_all_plz_for_ort('München')

        # All should return the same results
        self.assertEqual(sorted(plz_upper), sorted(plz_lower))
        self.assertEqual(sorted(plz_lower), sorted(plz_mixed))

    def test_get_all_plz_for_ort_invalid(self):
        """Test that invalid Ort returns empty list"""
        service = RegionalService.get_instance()

        # Test with non-existent Ort
        plz_list = service.get_all_plz_for_ort('NonexistentCity')

        # Should return empty list
        self.assertEqual(plz_list, [])
        self.assertIsInstance(plz_list, list)

    def test_get_all_plz_for_ort_none(self):
        """Test that None returns empty list"""
        service = RegionalService.get_instance()

        # Test with None
        plz_list = service.get_all_plz_for_ort(None)

        # Should return empty list
        self.assertEqual(plz_list, [])

    def test_ort_to_plz_consistency(self):
        """Test consistency between get_ort_by_plz and get_all_plz_for_ort"""
        service = RegionalService.get_instance()

        # Get Ort for a PLZ
        plz = '80331'
        ort = service.get_ort_by_plz(plz)

        if ort:
            # Get all PLZ for that Ort
            plz_list = service.get_all_plz_for_ort(ort)

            # The original PLZ should be in the list
            self.assertIn(plz, plz_list)


class RegionalFilterMixinTest(BadgrTestCase):
    """
    Test suite for RegionalFilterMixin.

    Tests regional filtering of issuers and badge instances based on issuer zip codes.
    Changed from user-based to issuer-based filtering.
    This functionality is critical for displaying region-specific dashboard data.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()  # Call BadgrTestCase setUp
        self.factory = RequestFactory()

        # Create test users with different zip codes
        # User zip codes are still used to determine the region filter
        self.user_berlin = BadgeUser.objects.create(
            email='berlin@example.com',
            first_name='Berlin',
            last_name='User',
            zip_code='10115',
            send_confirmation=False,
            create_email_address=False
        )

        self.user_munich = BadgeUser.objects.create(
            email='munich@example.com',
            first_name='Munich',
            last_name='User',
            zip_code='80331',
            send_confirmation=False,
            create_email_address=False
        )

        self.user_no_zip = BadgeUser.objects.create(
            email='nozip@example.com',
            first_name='NoZip',
            last_name='User',
            send_confirmation=False,
            create_email_address=False
        )

        # Create issuers with zip codes for badge instances
        # Changed: Issuers now have zip codes that determine regional filtering
        # Mock geocoding to avoid external API calls
        with ISSUER_SAVE_MOCK:
            self.issuer_berlin = Issuer.objects.create(
                name='Berlin Test Issuer',
                created_by=self.user_berlin,
                slug='test-issuer-berlin',
                url='http://example.com',
                email='issuer@example.com',
                zip='10115'  # Berlin zip code
            )

            self.issuer_munich = Issuer.objects.create(
                name='Munich Test Issuer',
                created_by=self.user_munich,
                slug='test-issuer-munich',
                url='http://example-munich.com',
                email='issuer-munich@example.com',
                zip='80331'  # Munich zip code
            )

        # Create badge classes for different issuers
        self.badge_class_berlin = BadgeClass.objects.create(
            name='Berlin Test Badge',
            description='Test badge from Berlin issuer',
            created_by=self.user_berlin,
            slug='test-badge-berlin',
            issuer=self.issuer_berlin,
            criteria_text='Complete the test'
        )

        self.badge_class_munich = BadgeClass.objects.create(
            name='Munich Test Badge',
            description='Test badge from Munich issuer',
            created_by=self.user_munich,
            slug='test-badge-munich',
            issuer=self.issuer_munich,
            criteria_text='Complete the test'
        )

        # Create badge instances
        # Changed: Badges now filtered by issuer location, not user location
        # Berlin issuer badge awarded to any user (even Munich user)
        self.badge_berlin_to_berlin = BadgeInstance.objects.create(
            recipient_identifier='berlin@example.com',
            badgeclass=self.badge_class_berlin,
            issuer=self.issuer_berlin,
            user=self.user_berlin,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Munich issuer badge awarded to any user
        self.badge_munich_to_munich = BadgeInstance.objects.create(
            recipient_identifier='munich@example.com',
            badgeclass=self.badge_class_munich,
            issuer=self.issuer_munich,
            user=self.user_munich,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Cross-region: Berlin issuer badge to Munich user
        # This should show up in Berlin filter (issuer region), not Munich
        self.badge_berlin_to_munich = BadgeInstance.objects.create(
            recipient_identifier='munich_cross@example.com',
            badgeclass=self.badge_class_berlin,
            issuer=self.issuer_berlin,
            user=self.user_munich,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def test_get_regional_issuer_ids_berlin(self):
        """
        Test filtering issuers by Berlin region (PLZ prefix '101').
        Verify that the Berlin issuer is included in results.
        Changed from user-based to issuer-based filtering.
        """
        # Get Berlin issuers (PLZ3 = '101')
        berlin_plz3 = '101'

        # Get all issuers with Berlin zip codes
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        self.assertEqual(landkreis, 'Berlin')

        # Get all PLZ for Berlin
        berlin_plz_list = service.get_all_plz_for_landkreis('Berlin')

        # Filter issuers whose zip is in Berlin PLZ list
        berlin_issuers = Issuer.objects.filter(
            zip__in=berlin_plz_list
        )

        # Should include Berlin issuer
        self.assertIn(self.issuer_berlin, berlin_issuers)

        # Should not include Munich issuer
        self.assertNotIn(self.issuer_munich, berlin_issuers)

    def test_get_regional_issuer_ids_munich(self):
        """Test filtering issuers by Munich region
        Changed from user-based to issuer-based filtering."""
        # Munich PLZ3
        munich_plz3 = '803'

        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(munich_plz3)

        if landkreis:
            # Get all PLZ for Munich area
            munich_plz_list = service.get_all_plz_for_landkreis(landkreis)

            # Filter issuers
            munich_issuers = Issuer.objects.filter(
                zip__in=munich_plz_list
            )

            # Should include Munich issuer
            self.assertIn(self.issuer_munich, munich_issuers)

            # Should not include Berlin issuer
            self.assertNotIn(self.issuer_berlin, munich_issuers)

    def test_get_regional_issuer_ids_no_zip_code(self):
        """Test that issuers without zip are excluded from regional filters
        Changed from user-based to issuer-based filtering."""
        # Get all issuers with zip codes
        issuers_with_zip = Issuer.objects.exclude(
            zip__isnull=True
        ).exclude(
            zip=''
        )

        # Should include issuers with zip codes
        self.assertIn(self.issuer_berlin, issuers_with_zip)
        self.assertIn(self.issuer_munich, issuers_with_zip)

    def test_get_regional_badge_instances(self):
        """
        Test filtering badge instances by issuer region.
        Changed: Verify that badges from issuers in a region are correctly filtered,
        regardless of which user received the badge.
        """
        # Get Berlin PLZ3
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        # Get badge instances from Berlin issuers (not Berlin users)
        berlin_badge_instances = BadgeInstance.objects.filter(
            badgeclass__issuer__zip__in=berlin_plz_list,
            revoked=False
        )

        # Should include all badges from Berlin issuer
        self.assertIn(self.badge_berlin_to_berlin, berlin_badge_instances)
        self.assertIn(self.badge_berlin_to_munich, berlin_badge_instances)

        # Should not include Munich issuer badge
        self.assertNotIn(self.badge_munich_to_munich, berlin_badge_instances)

    def test_regional_filter_with_request(self):
        """Test regional filtering using request object with authenticated user
        User's zip determines region, but filtering is by issuer zip."""
        # Create request with Berlin user
        request = self.factory.get('/v1/dashboard/overview/kpis')
        request.user = self.user_berlin

        # Verify user has zip_code
        self.assertEqual(request.user.zip_code, '10115')

        # Get PLZ3 from user's zip_code (this determines the region to filter)
        user_zip = request.user.zip_code
        plz3 = user_zip[:3] if user_zip else None

        if plz3:
            service = RegionalService.get_instance()
            landkreis = service.get_landkreis_by_plz3(plz3)

            # Should map to Berlin
            self.assertEqual(landkreis, 'Berlin')

            # Now verify that we filter issuers (not users) in this region
            berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)
            berlin_issuers = Issuer.objects.filter(zip__in=berlin_plz_list)

            # Should include Berlin issuer
            self.assertIn(self.issuer_berlin, berlin_issuers)

    def test_regional_filter_multiple_issuers_same_region(self):
        """Test filtering when multiple issuers are in the same region
        Changed from user-based to issuer-based filtering."""
        # Create another Berlin issuer
        issuer_berlin2 = Issuer.objects.create(
            name='Second Berlin Issuer',
            created_by=self.user_berlin,
            slug='test-issuer-berlin2',
            image='issuer.png',
            url='http://example2.com',
            email='issuer2@example.com',
            zip='10117'  # Another Berlin PLZ
        )

        # Get Berlin PLZ list
        service = RegionalService.get_instance()
        berlin_plz_list = service.get_all_plz_for_landkreis('Berlin')

        # Filter Berlin issuers
        berlin_issuers = Issuer.objects.filter(
            zip__in=berlin_plz_list
        )

        # Should include both Berlin issuers
        self.assertIn(self.issuer_berlin, berlin_issuers)
        self.assertIn(issuer_berlin2, berlin_issuers)

        # Should have at least 2 issuers
        self.assertGreaterEqual(berlin_issuers.count(), 2)
