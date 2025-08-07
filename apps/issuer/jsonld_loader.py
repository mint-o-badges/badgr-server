from pyld.jsonld import set_document_loader, ContextResolver
from cachetools import LRUCache
import requests
import logging

logger = logging.getLogger(__name__)

_doc_cache = LRUCache(maxsize=100)
_resolved_context_cache = LRUCache(maxsize=1000)


# TODO: remove the logs here after some testing
def cached_document_loader(url, options=None):
    if url in _doc_cache:
        logger.debug(f"Cache hit for: {url}")
        return _doc_cache[url]
    logger.debug(f"Cache miss for: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        doc = {"contextUrl": None, "documentUrl": url, "document": response.json()}
        _doc_cache[url] = doc
        return doc
    except Exception as e:
        logger.warning(f"Failed to load context from {url}: {e}")
        raise


_context_resolver = ContextResolver(_resolved_context_cache, cached_document_loader)


def setup_jsonld_loader():
    set_document_loader(cached_document_loader)
    _precache_common_contexts()


def get_context_resolver():
    return _context_resolver


def _precache_common_contexts():
    urls = [
        "https://www.w3.org/ns/credentials/v2",
        "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
        "https://purl.imsglobal.org/spec/ob/v3p0/extensions.json",
    ]
    for url in urls:
        try:
            cached_document_loader(url)
        except Exception:
            logger.warning(f"Could not pre-cache: {url}")
