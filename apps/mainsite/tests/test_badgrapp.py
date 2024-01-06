from mainsite.models import BadgrApp

from mainsite.tests.base import APITransactionTestCase, CachingTestCase, SetupIssuerHelper, SetupUserHelper


class TestBadgrApp(SetupUserHelper, SetupIssuerHelper, APITransactionTestCase, CachingTestCase):
    def test_badgr_app_unique_default(self):
        ba_one = BadgrApp.objects.create(
            cors='one.example.com',
            signup_redirect='https://one.example.com/start'
        )
        ba_two = BadgrApp.objects.create(
            cors='two.example.com',
            signup_redirect='https://two.example.com/start'
        )

        self.assertTrue(ba_one.is_default, "The first BadgrApp created is going to be the default one")

        ba_two.is_default = True
        ba_two.save()

        self.assertTrue(ba_two.is_default)
        ba_one = BadgrApp.objects.get(pk=ba_one.pk)  # re-fetch from database
        self.assertFalse(ba_one.is_default, "After setting #2 to default, #1 is no longer default.")

    def test_badgr_app_default_settings_population(self):
        ba_one = BadgrApp.objects.create(
            cors='one.example.com',
            signup_redirect='https://one.example.com/start'
        )
        self.assertEqual(ba_one.ui_login_redirect, ba_one.signup_redirect)

    def test_default_badgrapp(self):
        ba_one = BadgrApp.objects.create(
            cors='one.example.com',
            signup_redirect='https://one.example.com/start'
        )
        ba_two = BadgrApp.objects.create(
            cors='two.example.com',
            signup_redirect='https://two.example.com/start'
        )

        self.assertEqual(BadgrApp.objects.get_current(None).id, ba_one.id)
        self.assertEqual(BadgrApp.objects.get_by_id_or_default(ba_two.id).id, ba_two.id)

    def test_get_current_autocreates_first_app(self):
        self.assertEqual(BadgrApp.objects.count(), 0)
        app = BadgrApp.objects.get_current(None)
        self.assertEqual(app.cors, 'localhost:4200')
        self.assertEqual(BadgrApp.objects.count(), 1)

    def test_get_by_id_or_default_autocreates(self):
        self.assertEqual(BadgrApp.objects.count(), 0)
        app = BadgrApp.objects.get_by_id_or_default()
        self.assertEqual(app.cors, 'localhost:4200')
        self.assertEqual(BadgrApp.objects.count(), 1)

        app_again = BadgrApp.objects.get_by_id_or_default(str(app.id))
        self.assertEqual(app_again.id, app.id)

    def test_get_by_id_multiple_objects_failsafe(self):
        ba_one = BadgrApp.objects.create(
            cors='one.example.com',
            signup_redirect='https://one.example.com/start'
        )
        ba_two = BadgrApp.objects.create(
            cors='two.example.com',
            signup_redirect='https://two.example.com/start'
        )

        # Dangerous updating
        BadgrApp.objects.all().update(is_default=True)
        self.assertEqual(BadgrApp.objects.filter(is_default=True).count(), 2)
        app = BadgrApp.objects.get_by_id_or_default()
        self.assertEqual(app.id, ba_one.id)
        self.assertEqual(BadgrApp.objects.filter(is_default=True).count(), 1)

    def test_get_by_id_stupid_datatypes(self):
        # Test that autocreation fallback replaces deleted BadgrApp
        for val in ['stupid', 0.5, '20']:
            app = BadgrApp.objects.get_by_id_or_default(val)
            self.assertEqual(BadgrApp.objects.count(), 1)
            self.assertEqual(app.cors, 'localhost:4200')
            app.delete()

    def test_get_by_id_or_pk(self):
        ba_one = BadgrApp.objects.get_by_id_or_default()
        ba_two = BadgrApp.objects.create(
            name='The Original and Best',
            cors='one.example.com',
            signup_redirect='https://one.example.com/start',
            is_default=False
        )

        user = self.setup_user()
        issuer = self.setup_issuer(owner=user)
        issuer.badgrapp = ba_two
        issuer.save()

        cached_badgrapp_a = issuer.cached_badgrapp

        ba_two.name = "A Pale Imitation"
        ba_two.save()

        cached_badgrapp_b = issuer.cached_badgrapp
        cached_badgrapp_c = BadgrApp.objects.get_by_id_or_default(ba_two.id)

        # issuer.cached_badgrapp should have updated
        self.assertNotEqual(cached_badgrapp_a.name, cached_badgrapp_b.name)
        self.assertEqual(cached_badgrapp_b.name, cached_badgrapp_c.name)
