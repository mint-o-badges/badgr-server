import os

from django.conf import settings
from mainsite import TOP_DIR

test_files_path = os.path.join(TOP_DIR, "apps", "badgrsocialauth", "testfiles")
attribute_map_dir = os.path.join(test_files_path, "attributemaps")
# metadata_sp_1 = os.path.join(test_files_path, 'metadata_sp_1.xml')
# metadata_sp_2 = os.path.join(test_files_path, 'metadata_sp_2.xml')
ipd_cert_path = os.path.join(test_files_path, "idp-test-cert.pem")
ipd_key_path = os.path.join(test_files_path, "idp-test-key.pem")
idp_xml_path = os.path.join(test_files_path, "idp.xml")
vo_metadata_path = os.path.join(test_files_path, "vo_metadata.xml")

CONFIG = {
    "entityid": "urn:mace:example.com:saml:roland:sp",
    "name": "urn:mace:example.com:saml:roland:sp",
    "description": "My own SP",
    "service": {
        "sp": {
            "endpoints": {
                "assertion_consumer_service": ["http://lingon.catalogix.se:8087/"],
            },
            "required_attributes": ["surName", "givenName", "mail"],
            "optional_attributes": ["title"],
            "idp": ["urn:mace:example.com:saml:roland:idp"],
            "requested_attributes": [
                {
                    "name": "http://eidas.europa.eu/attributes/naturalperson/DateOfBirth",
                    "required": False,
                },
                {
                    "friendly_name": "PersonIdentifier",
                    "required": True,
                },
                {
                    "friendly_name": "PlaceOfBirth",
                },
            ],
            # 'authn_requests_signed': True,
            # 'logout_requests_signed': True,
            # 'want_assertions_signed': True,
        }
    },
    "debug": 1,
    "key_file": ipd_key_path,
    "cert_file": ipd_cert_path,
    # "encryption_keypairs": [{"key_file": full_path("test_1.key"), "cert_file": full_path("test_1.crt")},
    #                         {"key_file": full_path("test_2.key"), "cert_file": full_path("test_2.crt")}],
    # "ca_certs": full_path("cacerts.txt"),
    "xmlsec_binary": getattr(settings, "XMLSEC_BINARY_PATH", None),
    "metadata": {
        "local": [idp_xml_path, vo_metadata_path],
    },
    "virtual_organization": {
        "urn:mace:example.com:it:tek": {
            "nameid_format": "urn:oid:1.3.6.1.4.1.1466.115.121.1.15-NameID",
            "common_identifier": "umuselin",
        }
    },
    "subject_data": "subject_data.db",
    "accepted_time_diff": 60,
    "attribute_map_dir": attribute_map_dir,
    "valid_for": 6,
    "organization": {
        "name": ("AB Exempel", "se"),
        "display_name": ("AB Exempel", "se"),
        "url": "http://www.example.org",
    },
    "contact_person": [
        {
            "given_name": "Roland",
            "sur_name": "Hedberg",
            "telephone_number": "+46 70 100 0000",
            "email_address": ["tech@eample.com", "tech@example.org"],
            "contact_type": "technical",
        },
    ],
    # "logger": {
    #     "rotating": {
    #         "filename": full_path("sp.log"),
    #         "maxBytes": 100000,
    #         "backupCount": 5,
    #     },
    #     "loglevel": "info",
    # }
}
