from django.urls import re_path

from backpack.views import (
    LegacyBadgeShareRedirectView,
    RedirectSharedCollectionView,
    LegacyCollectionShareRedirectView,
)

urlpatterns = [
    # legacy redirects
    re_path(
        r"^share/?collection/(?P<share_hash>[^/]+)(/embed)?$",
        RedirectSharedCollectionView.as_view(),
        name="redirect_backpack_shared_collection",
    ),
    re_path(
        r"^share/?badge/(?P<share_hash>[^/]+)$",
        LegacyBadgeShareRedirectView.as_view(),
        name="legacy_redirect_backpack_shared_badge",
    ),
    re_path(
        r"^earner/collections/(?P<pk>[^/]+)/(?P<share_hash>[^/]+)$",
        LegacyCollectionShareRedirectView.as_view(),
        name="legacy_shared_collection",
    ),
    re_path(
        r"^earner/collections/(?P<pk>[^/]+)/(?P<share_hash>[^/]+)/embed$",
        LegacyCollectionShareRedirectView.as_view(),
        name="legacy_shared_collection_embed",
    ),
]
