import aniso8601
import hashlib
import pytz
import re
from urllib.parse import urlparse, urlunparse

from django.urls import resolve, Resolver404
from django.utils import timezone

from mainsite.utils import OriginSetting


OBI_VERSION_CONTEXT_IRIS = {
    '1_1': 'https://w3id.org/openbadges/v1',
    '2_0': 'https://w3id.org/openbadges/v2',
}

CURRENT_OBI_VERSION = '2_0'
CURRENT_OBI_CONTEXT_IRI = OBI_VERSION_CONTEXT_IRIS.get(CURRENT_OBI_VERSION)

# assertions that were baked and saved to BadgeInstance.image used this version
UNVERSIONED_BAKED_VERSION = '2_0'


def get_obi_context(obi_version):
    context_iri = OBI_VERSION_CONTEXT_IRIS.get(obi_version, None)
    if context_iri is None:
        obi_version = CURRENT_OBI_VERSION
        context_iri = CURRENT_OBI_CONTEXT_IRI
    return (obi_version, context_iri)


def add_obi_version_ifneeded(url, obi_version):
    if obi_version == CURRENT_OBI_VERSION:
        return url
    if not url.startswith(OriginSetting.HTTP):
        return url
    return "{url}{sep}v={obi_version}".format(
        url=url,
        sep='&' if '?' in url else '?',
        obi_version=obi_version)


def generate_sha256_hashstring(identifier, salt=None):
    key = '{}{}'.format(identifier, salt if salt is not None else "")
    return 'sha256$' + hashlib.sha256(key.encode('utf-8')).hexdigest()


def generate_md5_hashstring(identifier, salt=None):
    key = '{}{}'.format(identifier, salt if salt is not None else "")
    return 'md5$' + hashlib.md5(key.encode('utf-8')).hexdigest()


def generate_rebaked_filename(oldname, badgeclass_filename):
    parts = oldname.split('.')
    badgeclass_filename_parts = badgeclass_filename.split('.')
    ext = badgeclass_filename_parts.pop()
    parts.append('rebaked')
    return 'assertion-{}.{}'.format(hashlib.md5(''.join(parts).encode('utf-8')).hexdigest(), ext)


def is_probable_url(string):
    earl = re.compile(r'^https?')
    if string is None:
        return False
    return earl.match(string)


def obscure_email_address(email):
    charlist = list(email)

    return ''.join(letter if letter in ('@', '.',) else '*' for letter in charlist)


def get_badgeclass_by_identifier(identifier):
    """
    Finds a Issuer.BadgeClass by an identifier that can be either:
        - JSON-ld id
        - BadgeClass.id
        - BadgeClass.slug
    """

    from issuer.models import BadgeClass

    # attempt to resolve identifier as JSON-ld id
    if identifier.startswith(OriginSetting.HTTP):
        try:
            resolver_match = resolve(identifier.replace(OriginSetting.HTTP, ''))
            if resolver_match:
                entity_id = resolver_match.kwargs.get('entity_id', None)
                if entity_id:
                    try:
                        return BadgeClass.cached.get(entity_id=entity_id)
                    except BadgeClass.DoesNotExist:
                        pass
        except Resolver404:
            pass

    # attempt to resolve as BadgeClass.slug
    try:
        return BadgeClass.cached.get(slug=identifier)
    except BadgeClass.DoesNotExist:
        pass

    # attempt to resolve as BadgeClass.entity_id
    try:
        return BadgeClass.cached.get(entity_id=identifier)
    except (BadgeClass.DoesNotExist, ValueError):
        pass

    # attempt to resolve as JSON-ld of external badge
    try:
        return BadgeClass.cached.get(source_url=identifier)
    except BadgeClass.DoesNotExist:
        pass

    # nothing found
    return None


def parse_original_datetime(t, tzinfo=pytz.utc):
    try:
        result = timezone.datetime.fromtimestamp(float(t), pytz.utc).isoformat()
    except (ValueError, TypeError):
        try:
            dt = aniso8601.parse_datetime(t)
            if not timezone.is_aware(dt):
                dt = pytz.utc.localize(dt)
            elif timezone.is_aware(dt) and dt.tzinfo != tzinfo:
                dt = dt.astimezone(tzinfo)
            result = dt.isoformat()
        except (ValueError, TypeError):
            dt = timezone.datetime.strptime(t, '%Y-%m-%d')
            if not timezone.is_aware(dt):
                dt = pytz.utc.localize(dt)
            elif timezone.is_aware(dt) and dt.tzinfo != tzinfo:
                dt = dt.astimezone(tzinfo).isoformat()
            result = dt.isoformat()

    if result and result.endswith('00:00'):
        return result[:-6] + 'Z'
    return result


def request_authenticated_with_server_admin_token(request):
    try:
        return 'rw:serverAdmin' in set(request.auth.scope.split())
    except AttributeError:
        return False


def sanitize_id(recipient_identifier, identifier_type, allow_uppercase=False):
    if identifier_type == 'email':
        return recipient_identifier if allow_uppercase else recipient_identifier.lower()
    elif identifier_type == 'url':
        p = urlparse(recipient_identifier)
        return urlunparse((
            p.scheme,
            p.netloc.lower(),
            p.path,
            p.params,
            p.query,
            p.fragment,
        ))
    return recipient_identifier
