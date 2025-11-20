# encoding: utf-8


from django.urls import re_path

from backpack.api import (
    BackpackAssertionList,
    BackpackAssertionDetail,
    BackpackCollectionList,
    BackpackCollectionDetail,
    BackpackAssertionDetailImage,
    BackpackImportBadge,
    ShareBackpackCollection,
    ShareBackpackAssertion,
    BadgesFromUser,
)

urlpatterns = [
    re_path(
        r"^import$", BackpackImportBadge.as_view(), name="v2_api_backpack_import_badge"
    ),
    re_path(
        r"^assertions$",
        BackpackAssertionList.as_view(),
        name="v2_api_backpack_assertion_list",
    ),
    re_path(
        r"^assertions/(?P<entity_id>[^/]+)$",
        BackpackAssertionDetail.as_view(),
        name="v2_api_backpack_assertion_detail",
    ),
    re_path(
        r"^assertions/(?P<entity_id>[^/]+)/image$",
        BackpackAssertionDetailImage.as_view(),
        name="v2_api_backpack_assertion_detail_image",
    ),
    re_path(
        r"^collections$",
        BackpackCollectionList.as_view(),
        name="v2_api_backpack_collection_list",
    ),
    re_path(
        r"^collections/(?P<entity_id>[^/]+)$",
        BackpackCollectionDetail.as_view(),
        name="v2_api_backpack_collection_detail",
    ),
    re_path(
        r"^share/assertion/(?P<entity_id>[^/]+)$",
        ShareBackpackAssertion.as_view(),
        name="v2_api_share_assertion",
    ),
    re_path(
        r"^share/collection/(?P<entity_id>[^/]+)$",
        ShareBackpackCollection.as_view(),
        name="v2_api_share_collection",
    ),
    re_path(
        r"^(?P<email>[^/]+)$",
        BadgesFromUser().as_view(),
        name="v2_api_badges_from_user",
    ),
]
