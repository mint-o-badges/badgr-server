# encoding: utf-8
import responses
from django.core.exceptions import ValidationError
from django.test import override_settings
from mainsite.blacklist import generate_hash
from mainsite.tests import BadgrTestCase, SetupIssuerHelper

SETTINGS_OVERRIDE = {
    "BADGR_BLACKLIST_API_KEY": "blacklistkeyexample123",
    "BADGR_BLACKLIST_QUERY_ENDPOINT": "https://example_blacklist.com/query",
}


def _generate_blacklist_url(identifier, id_type="email"):
    hashed_identifier = generate_hash(id_type, identifier)
    return "{endpoint}?id={recipient_id_hash}".format(
        endpoint=SETTINGS_OVERRIDE["BADGR_BLACKLIST_QUERY_ENDPOINT"],
        recipient_id_hash=hashed_identifier,
    )


def _generate_blacklist_response_body(identifier, id_type="email"):
    return [{"id": generate_hash(id_type, identifier)}]


class AssertionBlacklistTests(SetupIssuerHelper, BadgrTestCase):
    def setUp(self):
        super(AssertionBlacklistTests, self).setUp()
        self.issuer_owner = self.setup_user()
        self.issuer = self.setup_issuer(owner=self.issuer_owner)
        self.badgeclass = self.setup_badgeclass(issuer=self.issuer)

    @override_settings(**SETTINGS_OVERRIDE)
    @responses.activate
    def test_blacklist_presence_blocks_award(self):
        email = "testblacklisteduser@example.com"
        responses.add(
            responses.GET,
            _generate_blacklist_url(email),
            json=_generate_blacklist_response_body(email),
        )

        with self.assertRaises(ValidationError):
            self.badgeclass.issue(email)
