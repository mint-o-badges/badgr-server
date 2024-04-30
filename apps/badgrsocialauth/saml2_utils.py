from saml2.config import Config
from saml2.metadata import (
    entities_descriptor,
    entity_descriptor,
    sign_entity_descriptor,
)
from saml2.sigver import security_context
from saml2.validate import valid_instance


def metadata_tostring_fix(desc, nspair, xmlstring=""):
    MDNS = '"urn:oasis:names:tc:SAML:2.0:metadata"'
    bMDNS = b'"urn:oasis:names:tc:SAML:2.0:metadata"'
    XMLNSXS = ' xmlns:xs="http://www.w3.org/2001/XMLSchema"'
    bXMLNSXS = b' xmlns:xs="http://www.w3.org/2001/XMLSchema"'
    if not xmlstring:
        xmlstring = desc.to_string(nspair)

    try:
        if '"xs:string"' in xmlstring and XMLNSXS not in xmlstring:
            xmlstring = xmlstring.replace(MDNS, MDNS + XMLNSXS)
    except TypeError:
        if b'"xs:string"' in xmlstring and bXMLNSXS not in xmlstring:
            xmlstring = xmlstring.replace(bMDNS, bMDNS + bXMLNSXS)

    return xmlstring


def create_metadata_string(
    configfile,
    config=None,
    valid=None,
    cert=None,
    keyfile=None,
    mid=None,
    name=None,
    sign=None,
):
    """
    TODO: REMOVE THIS FUNCTION AFTER pysaml2 library is updated. to fix the above metadata_tostring_fix function
    """
    valid_for = 0
    nspair = {"xs": "http://www.w3.org/2001/XMLSchema"}
    # paths = [".", "/opt/local/bin"]

    if valid:
        valid_for = int(valid)  # Hours

    eds = []
    if config is None:
        if configfile.endswith(".py"):
            configfile = configfile[:-3]
        config = Config().load_file(configfile, metadata_construction=True)
    eds.append(entity_descriptor(config))

    conf = Config()
    conf.key_file = config.key_file or keyfile
    conf.cert_file = config.cert_file or cert
    conf.debug = 1
    conf.xmlsec_binary = config.xmlsec_binary
    secc = security_context(conf)

    if mid:
        eid, xmldoc = entities_descriptor(eds, valid_for, name, mid, sign, secc)
    else:
        eid = eds[0]
        if sign:
            eid, xmldoc = sign_entity_descriptor(eid, mid, secc)
        else:
            xmldoc = None

    valid_instance(eid)
    return metadata_tostring_fix(eid, nspair, xmldoc)
