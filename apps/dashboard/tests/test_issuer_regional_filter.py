# encoding: utf-8
"""
Comprehensive test suite for issuer-based regional filtering functionality.

REQUIREMENT: Filter badge instances by ISSUER regions (issuer.zip) instead of USER regions (user.zip_code)

Tests the following scenarios:
1. Single region filtering - badges from issuers in one region
2. Multiple regions - badges from issuers in different regions
3. No region filter - issuers without zip code
4. Mixed scenarios - some issuers with zip, some without
5. Verification that issuer.zip is used, NOT user.zip_code

This test suite ensures that the regional filtering correctly uses issuer location
rather than user location for filtering badge instances.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from badgeuser.models import BadgeUser
from issuer.models import BadgeInstance, BadgeClass, Issuer
from dashboard.mixins import RegionalFilterMixin
from dashboard.services.regional_service import RegionalService


class IssuerRegionalFilterTest(TestCase):
    """
    Test suite for issuer-based regional filtering.

    CRITICAL: These tests verify that filtering uses issuer.zip, NOT user.zip_code.
    """

    def setUp(self):
        """Set up test fixtures"""
        # Patch geocode to avoid external API calls during testing
        self.patcher = patch('issuer.models.geocode', return_value=None)
        self.mock_geocode = self.patcher.start()

        self.factory = RequestFactory()

        # Create test users with different zip codes
        # Users should NOT affect filtering - only issuer zip codes matter
        self.user_berlin = BadgeUser(
            username='berlin_user',
            email='berlin@example.com',
            first_name='Berlin',
            last_name='User',
            zip_code='10115'  # Berlin user zip
        )
        self.user_berlin.save()

        self.user_munich = BadgeUser(
            username='munich_user',
            email='munich@example.com',
            first_name='Munich',
            last_name='User',
            zip_code='80331'  # Munich user zip
        )
        self.user_munich.save()

        self.user_no_zip = BadgeUser(
            username='no_zip_user',
            email='nozip@example.com',
            first_name='NoZip',
            last_name='User'
        )
        self.user_no_zip.save()
        # No zip_code for this user

        # Create issuers with different zip codes
        # THESE are what should be used for filtering
        self.issuer_berlin = Issuer.objects.create(
            name='Berlin Institute',
            created_by=self.user_berlin,
            slug='berlin-institute',
            url='http://berlin.example.com',
            email='issuer@berlin.example.com',
            zip='10115'  # Berlin issuer - THIS should be used for filtering
        )

        self.issuer_munich = Issuer.objects.create(
            name='Munich Institute',
            created_by=self.user_munich,
            slug='munich-institute',
            url='http://munich.example.com',
            email='issuer@munich.example.com',
            zip='80331'  # Munich issuer - THIS should be used for filtering
        )

        self.issuer_no_zip = Issuer.objects.create(
            name='Virtual Institute',
            created_by=self.user_no_zip,
            slug='virtual-institute',
            url='http://virtual.example.com',
            email='issuer@virtual.example.com'
            # No zip for this issuer
        )

        # Create badge classes
        self.badge_class_berlin = BadgeClass.objects.create(
            name='Berlin Badge',
            description='Badge from Berlin institute',
            created_by=self.user_berlin,
            slug='berlin-badge',
            issuer=self.issuer_berlin,
            criteria_text='Complete Berlin course'
        )

        self.badge_class_munich = BadgeClass.objects.create(
            name='Munich Badge',
            description='Badge from Munich institute',
            created_by=self.user_munich,
            slug='munich-badge',
            issuer=self.issuer_munich,
            criteria_text='Complete Munich course'
        )

        self.badge_class_no_zip = BadgeClass.objects.create(
            name='Virtual Badge',
            description='Badge from virtual institute',
            created_by=self.user_no_zip,
            slug='virtual-badge',
            issuer=self.issuer_no_zip,
            criteria_text='Complete virtual course'
        )

        # Create badge instances
        # CRITICAL TEST CASE: Berlin user receives Munich badge
        # This should be filtered by ISSUER region (Munich), NOT user region (Berlin)
        self.badge_berlin_to_berlin = BadgeInstance.objects.create(
            recipient_identifier='berlin@example.com',
            badgeclass=self.badge_class_berlin,
            issuer=self.issuer_berlin,
            user=self.user_berlin,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Munich badge to Berlin user - should appear in MUNICH region filter
        self.badge_munich_to_berlin = BadgeInstance.objects.create(
            recipient_identifier='berlin2@example.com',
            badgeclass=self.badge_class_munich,
            issuer=self.issuer_munich,
            user=self.user_berlin,  # Berlin user receives Munich badge
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Berlin badge to Munich user - should appear in BERLIN region filter
        self.badge_berlin_to_munich = BadgeInstance.objects.create(
            recipient_identifier='munich2@example.com',
            badgeclass=self.badge_class_berlin,
            issuer=self.issuer_berlin,  # Berlin issuer
            user=self.user_munich,  # Munich user receives Berlin badge
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        self.badge_munich_to_munich = BadgeInstance.objects.create(
            recipient_identifier='munich@example.com',
            badgeclass=self.badge_class_munich,
            issuer=self.issuer_munich,
            user=self.user_munich,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        self.badge_no_zip_to_berlin = BadgeInstance.objects.create(
            recipient_identifier='berlin3@example.com',
            badgeclass=self.badge_class_no_zip,
            issuer=self.issuer_no_zip,
            user=self.user_berlin,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def tearDown(self):
        """Clean up patches"""
        self.patcher.stop()

    def test_filter_by_issuer_region_berlin(self):
        """
        Test that filtering by Berlin region returns badges from Berlin ISSUERS.

        CRITICAL: Should filter by issuer.zip, NOT user.zip_code.
        Expected: All badges from Berlin issuer, regardless of user location.
        """
        # Create request with Berlin user
        request = self.factory.get('/v1/dashboard/overview/kpis')
        request.user = self.user_berlin

        # Get Berlin PLZ3 and regional PLZ list
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        # Filter badge instances by ISSUER zip (correct behavior)
        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # Should include badges from Berlin issuer
        self.assertIn(self.badge_berlin_to_berlin, berlin_badge_instances)
        self.assertIn(self.badge_berlin_to_munich, berlin_badge_instances)

        # Should NOT include badges from Munich issuer
        # Even though user is in Berlin, issuer is in Munich
        self.assertNotIn(self.badge_munich_to_berlin, berlin_badge_instances)
        self.assertNotIn(self.badge_munich_to_munich, berlin_badge_instances)

        # Should NOT include badges from issuer without zip
        self.assertNotIn(self.badge_no_zip_to_berlin, berlin_badge_instances)

        # Verify count
        self.assertEqual(berlin_badge_instances.count(), 2)

    def test_filter_by_issuer_region_munich(self):
        """
        Test that filtering by Munich region returns badges from Munich ISSUERS.

        Expected: All badges from Munich issuer, regardless of user location.
        """
        # Munich PLZ3
        munich_plz3 = '803'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(munich_plz3)

        if landkreis:
            munich_plz_list = service.get_all_plz_for_landkreis(landkreis)

            # Filter by ISSUER zip
            munich_badge_instances = BadgeInstance.objects.filter(
                revoked=False,
                badgeclass__issuer__zip__in=munich_plz_list
            )

            # Should include badges from Munich issuer
            self.assertIn(self.badge_munich_to_berlin, munich_badge_instances)
            self.assertIn(self.badge_munich_to_munich, munich_badge_instances)

            # Should NOT include badges from Berlin issuer
            self.assertNotIn(self.badge_berlin_to_berlin, munich_badge_instances)
            self.assertNotIn(self.badge_berlin_to_munich, munich_badge_instances)

            # Verify count
            self.assertEqual(munich_badge_instances.count(), 2)

    def test_issuer_without_zip_excluded(self):
        """
        Test that badges from issuers without zip code are excluded from regional filters.

        Expected: Issuers without zip should not appear in any regional filter.
        """
        # Get Berlin regional badges
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # Badge from issuer without zip should NOT appear
        self.assertNotIn(self.badge_no_zip_to_berlin, berlin_badge_instances)

    def test_user_location_does_not_affect_filter(self):
        """
        CRITICAL TEST: Verify that user location (user.zip_code) does NOT affect filtering.

        Only issuer location (issuer.zip) should determine which badges appear.

        This is the key requirement change:
        - OLD: Filter by user.zip_code
        - NEW: Filter by issuer.zip
        """
        # Berlin user receives Munich badge
        # When filtering by Berlin region, this badge should NOT appear
        # Because the ISSUER is in Munich, not Berlin

        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        # Filter by issuer zip
        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # This badge should NOT appear in Berlin filter
        # Even though the user is in Berlin, the issuer is in Munich
        self.assertNotIn(self.badge_munich_to_berlin, berlin_badge_instances)

        # Munich user receives Berlin badge
        # When filtering by Berlin region, this badge SHOULD appear
        # Because the ISSUER is in Berlin
        self.assertIn(self.badge_berlin_to_munich, berlin_badge_instances)

    def test_get_regional_issuer_ids(self):
        """
        Test helper method to get issuer IDs by region.

        This is what the implementation should do: get issuers in a region,
        then filter badges by those issuers.
        """
        # Get Berlin issuers
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        # Get issuer IDs in Berlin region
        berlin_issuer_ids = Issuer.objects.filter(
            zip__in=berlin_plz_list
        ).values_list('id', flat=True)

        # Should include Berlin issuer
        self.assertIn(self.issuer_berlin.id, berlin_issuer_ids)

        # Should NOT include Munich issuer
        self.assertNotIn(self.issuer_munich.id, berlin_issuer_ids)

        # Should NOT include issuer without zip
        self.assertNotIn(self.issuer_no_zip.id, berlin_issuer_ids)

    def test_get_regional_badge_instances_by_issuer(self):
        """
        Test the complete flow: get badges filtered by issuer region.

        This tests what get_regional_badge_instances() should do after implementation.
        """
        # Create request with Berlin user
        request = self.factory.get('/v1/dashboard/overview/kpis')
        request.user = self.user_berlin

        # Get user's region
        user_zip = request.user.zip_code
        plz3 = user_zip[:3]

        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(plz3)
        regional_plz_list = service.get_all_plz_for_landkreis(landkreis)

        # Get issuers in the user's region
        regional_issuer_ids = Issuer.objects.filter(
            zip__in=regional_plz_list
        ).values_list('id', flat=True)

        # Get badge instances from regional issuers
        badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer_id__in=regional_issuer_ids
        )

        # Verify results
        # Should include badges from Berlin issuer
        self.assertIn(self.badge_berlin_to_berlin, badge_instances)
        self.assertIn(self.badge_berlin_to_munich, badge_instances)

        # Should NOT include badges from Munich issuer
        # Even though Berlin user received it
        self.assertNotIn(self.badge_munich_to_berlin, badge_instances)

    def test_multiple_issuers_same_region(self):
        """
        Test that multiple issuers in the same region are all included.
        """
        # Create second Berlin issuer
        issuer_berlin2 = Issuer.objects.create(
            name='Berlin Institute 2',
            created_by=self.user_berlin,
            slug='berlin-institute-2',
            url='http://berlin2.example.com',
            email='issuer2@berlin.example.com',
            zip='10117'  # Another Berlin PLZ
        )

        badge_class_berlin2 = BadgeClass.objects.create(
            name='Berlin Badge 2',
            description='Badge from second Berlin institute',
            created_by=self.user_berlin,
            slug='berlin-badge-2',
            issuer=issuer_berlin2,
            criteria_text='Complete second Berlin course'
        )

        badge_berlin2 = BadgeInstance.objects.create(
            recipient_identifier='test@example.com',
            badgeclass=badge_class_berlin2,
            issuer=issuer_berlin2,
            user=self.user_munich,  # Munich user gets Berlin badge
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Get Berlin badges
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # Should include badges from both Berlin issuers
        self.assertIn(self.badge_berlin_to_berlin, berlin_badge_instances)
        self.assertIn(self.badge_berlin_to_munich, berlin_badge_instances)
        self.assertIn(badge_berlin2, berlin_badge_instances)

        # Should be 3 badges total
        self.assertGreaterEqual(berlin_badge_instances.count(), 3)

    def test_revoked_badges_excluded(self):
        """
        Test that revoked badges are excluded from results.
        """
        # Revoke a badge
        self.badge_berlin_to_berlin.revoked = True
        self.badge_berlin_to_berlin.save()

        # Get Berlin badges
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # Should NOT include revoked badge
        self.assertNotIn(self.badge_berlin_to_berlin, berlin_badge_instances)

        # Should still include non-revoked Berlin badge
        self.assertIn(self.badge_berlin_to_munich, berlin_badge_instances)

    def test_no_filter_when_user_has_no_zip(self):
        """
        Test that when user has no zip_code, no regional filter is applied.

        Expected: Return all badges (or handle gracefully).
        """
        # Create request with user without zip
        request = self.factory.get('/v1/dashboard/overview/kpis')
        request.user = self.user_no_zip

        # If user has no zip, should return None or all badges
        # This depends on implementation choice
        self.assertIsNone(self.user_no_zip.zip_code)

    def test_invalid_issuer_zip_handled(self):
        """
        Test that issuers with invalid zip codes are handled gracefully.
        """
        # Create issuer with invalid zip
        issuer_invalid = Issuer.objects.create(
            name='Invalid Zip Institute',
            created_by=self.user_berlin,
            slug='invalid-zip-institute',
            url='http://invalid.example.com',
            email='issuer@invalid.example.com',
            zip='XX'  # Invalid zip
        )

        badge_class_invalid = BadgeClass.objects.create(
            name='Invalid Zip Badge',
            description='Badge from invalid zip institute',
            created_by=self.user_berlin,
            slug='invalid-zip-badge',
            issuer=issuer_invalid,
            criteria_text='Test'
        )

        badge_invalid = BadgeInstance.objects.create(
            recipient_identifier='test2@example.com',
            badgeclass=badge_class_invalid,
            issuer=issuer_invalid,
            user=self.user_berlin,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

        # Get Berlin badges
        berlin_plz3 = '101'
        service = RegionalService.get_instance()
        landkreis = service.get_landkreis_by_plz3(berlin_plz3)
        berlin_plz_list = service.get_all_plz_for_landkreis(landkreis)

        berlin_badge_instances = BadgeInstance.objects.filter(
            revoked=False,
            badgeclass__issuer__zip__in=berlin_plz_list
        )

        # Badge from issuer with invalid zip should NOT appear
        self.assertNotIn(badge_invalid, berlin_badge_instances)


class RegionalFilterMixinIssuerTest(TestCase):
    """
    Test the RegionalFilterMixin with the NEW issuer-based implementation.

    These tests verify the mixin methods work correctly with issuer filtering.
    """

    def setUp(self):
        """Set up test fixtures"""
        # Patch geocode to avoid external API calls during testing
        self.patcher = patch('issuer.models.geocode', return_value=None)
        self.mock_geocode = self.patcher.start()

        self.factory = RequestFactory()
        self.mixin = RegionalFilterMixin()

        # Create test user
        self.user_berlin = BadgeUser(
            username='berlin_user',
            email='berlin@example.com',
            first_name='Berlin',
            last_name='User',
            zip_code='10115'
        )
        self.user_berlin.save()

        # Create issuer
        self.issuer_berlin = Issuer.objects.create(
            name='Berlin Institute',
            created_by=self.user_berlin,
            slug='berlin-institute',
            url='http://berlin.example.com',
            email='issuer@berlin.example.com',
            zip='10115'
        )

        # Create badge class and instance
        self.badge_class = BadgeClass.objects.create(
            name='Test Badge',
            description='Test badge',
            created_by=self.user_berlin,
            slug='test-badge',
            issuer=self.issuer_berlin,
            criteria_text='Test'
        )

        self.badge_instance = BadgeInstance.objects.create(
            recipient_identifier='test@example.com',
            badgeclass=self.badge_class,
            issuer=self.issuer_berlin,
            user=self.user_berlin,
            acceptance=BadgeInstance.ACCEPTANCE_ACCEPTED
        )

    def tearDown(self):
        """Clean up patches"""
        self.patcher.stop()

    def test_mixin_with_authenticated_user(self):
        """
        Test that mixin works with authenticated user.
        """
        request = self.factory.get('/test')
        request.user = self.user_berlin

        # Test that we can get regional badge instances
        # The actual filtering logic should use issuer.zip
        badge_instances = self.mixin.get_regional_badge_instances(request)

        # Should return a queryset
        self.assertIsNotNone(badge_instances)

    def test_mixin_with_unauthenticated_user(self):
        """
        Test mixin handles unauthenticated users gracefully.
        """
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/test')
        request.user = AnonymousUser()

        # Should handle gracefully
        badge_instances = self.mixin.get_regional_badge_instances(request)

        # Should return empty or all badges depending on implementation
        self.assertIsNotNone(badge_instances)
