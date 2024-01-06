from django.test import override_settings
from django.utils import timezone
from django.utils.timezone import timedelta

from mainsite.tests.base import BadgrTestCase
from mainsite.utils import (clamped_backoff_in_seconds, clear_backoff_count_for_ip,
                            iterate_backoff_count,)

SETTINGS_OVERRIDE = {
    'TOKEN_BACKOFF_MAXIMUM_SECONDS': 3600,
    'TOKEN_BACKOFF_PERIOD_SECONDS': 2
}


class BackoffTests(BadgrTestCase):
    @override_settings(**SETTINGS_OVERRIDE)
    def test_clamped_backoff(self):
        for m, n in [
            (0, 1),
            (1, 2),
            (2, 4),
            (3, 8),
            (4, 16),
            (5, 32),
            (6, 64),
            (7, 128),
            (8, 256),
            (9, 512),
            (10, 1024),
            (11, 2048),
            (12, 3600),
            (13, 3600),
            (400, 3600),
        ]:
            backoff = clamped_backoff_in_seconds(m)
            self.assertEqual(backoff, n, "For count {}, backoff should = {} seconds, not {}".format(m, n, backoff))

    @override_settings(**SETTINGS_OVERRIDE)
    def test_iterate_backoff_count(self):
        ip1 = '1.2.3.4'
        backoff = iterate_backoff_count(None, ip1)

        new_backoff = iterate_backoff_count(backoff, ip1)
        self.assertEqual(new_backoff[ip1]['count'], 2)

    def test_backoff_manipulation_for_client_ip(self):
        ip1 = '1.2.3.4'
        ip2 = '4.5.6.7'
        backoff = iterate_backoff_count(None, ip1)
        self.assertEqual(backoff[ip1]['count'], 1)

        backoff = iterate_backoff_count(backoff, ip1)
        backoff = iterate_backoff_count(backoff, ip2)
        self.assertEqual(backoff[ip1]['count'], 2)
        self.assertEqual(backoff[ip2]['count'], 1)

        backoff = clear_backoff_count_for_ip(backoff, ip1)
        self.assertIsNone(backoff.get(ip1))
        self.assertEqual(backoff[ip2]['count'], 1)

    def test_backoff_expunging_past_entries(self):
        ip1 = '1.2.3.4'
        ip2 = '4.5.6.7'
        backoff = iterate_backoff_count(None, ip1)
        backoff = iterate_backoff_count(backoff, ip2)
        backoff = iterate_backoff_count(backoff, ip2)
        backoff[ip2]['until'] = timezone.now() - timedelta(hours=2)

        backoff = iterate_backoff_count(backoff, ip1)
        self.assertIsNone(backoff.get(ip2))  # The expired "until" has been expunged
