from django.conf.urls import url

from backpack.api import (
    BackpackAssertionList,
    BackpackAssertionDetail,
    BackpackAssertionDetailImage,
    BackpackCollectionList,
    BackpackCollectionDetail,
    BackpackSkillList,
    ImportedBadgeInstanceDetail,
    ImportedBadgeInstanceList,
    ShareBackpackAssertion,
    ShareBackpackCollection,
)
from backpack.api_v1 import (
    CollectionLocalBadgeInstanceList,
    CollectionLocalBadgeInstanceDetail,
    CollectionGenerateShare,
)

from backpack.views import collectionPdf, pdf

urlpatterns = [
    url(
        r"^badges$",
        BackpackAssertionList.as_view(),
        name="v1_api_localbadgeinstance_list",
    ),
    url(
        r"^badges/(?P<slug>[^/]+)$",
        BackpackAssertionDetail.as_view(),
        name="v1_api_localbadgeinstance_detail",
    ),
    url(
        r"^badges/(?P<slug>[^/]+)/image$",
        BackpackAssertionDetailImage.as_view(),
        name="v1_api_localbadgeinstance_image",
    ),
    url(r"^skills$", BackpackSkillList.as_view(), name="v1_api_skills_list"),
    url(
        r"^collections$",
        BackpackCollectionList.as_view(),
        name="v1_api_collection_list",
    ),
    url(
        r"^collections/(?P<slug>[-\w]+)$",
        BackpackCollectionDetail.as_view(),
        name="v1_api_collection_detail",
    ),
    # legacy v1 endpoints
    url(
        r"^collections/(?P<slug>[-\w]+)/badges$",
        CollectionLocalBadgeInstanceList.as_view(),
        name="v1_api_collection_badges",
    ),
    url(
        r"^collections/(?P<collection_slug>[-\w]+)/badges/(?P<slug>[^/]+)$",
        CollectionLocalBadgeInstanceDetail.as_view(),
        name="v1_api_collection_localbadgeinstance_detail",
    ),
    url(
        r"^collections/(?P<slug>[-\w]+)/share$",
        CollectionGenerateShare.as_view(),
        name="v1_api_collection_generate_share",
    ),
    url(
        r"^share/badge/(?P<slug>[^/]+)$",
        ShareBackpackAssertion.as_view(),
        name="v1_api_analytics_share_badge",
    ),
    url(
        r"^share/collection/(?P<slug>[^/]+)$",
        ShareBackpackCollection.as_view(),
        name="v1_api_analytics_share_collection",
    ),
    url(r"^badges/pdf/(?P<slug>[^/]+)$", pdf, name="generate-pdf"),
    url(
        r"^collections/pdf/(?P<slug>[^/]+)$",
        collectionPdf,
        name="generate-collection-pdf",
    ),
    url(
        r"^imported-badges$",
        ImportedBadgeInstanceList.as_view(),
        name="v1_api_importedbadge_list",
    ),
    url(
        r"^imported-badges/(?P<entity_id>[^/]+)$",
        ImportedBadgeInstanceDetail.as_view(),
        name="v1_api_importedbadge_detail",
    ),
]
