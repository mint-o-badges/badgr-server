from django.urls import re_path

from issuer.api import (
    IssuerList,
    IssuerDetail,
    IssuerBadgeClassList,
    BadgeClassDetail,
    BadgeInstanceList,
    BadgeInstanceDetail,
    IssuerBadgeInstanceList,
    AllBadgeClassesList,
    BatchAssertionsIssue,
    BatchAssertionsRevoke,
    IssuerTokensList,
    AssertionsChangedSince,
    BadgeClassesChangedSince,
    IssuersChangedSince,
)

urlpatterns = [
    re_path(r"^issuers$", IssuerList.as_view(), name="v2_api_issuer_list"),
    re_path(
        r"^issuers/changed$",
        IssuersChangedSince.as_view(),
        name="v2_api_issuers_changed_list",
    ),
    re_path(
        r"^issuers/(?P<entity_id>[^/]+)$",
        IssuerDetail.as_view(),
        name="v2_api_issuer_detail",
    ),
    re_path(
        r"^issuers/(?P<entity_id>[^/]+)/assertions$",
        IssuerBadgeInstanceList.as_view(),
        name="v2_api_issuer_assertion_list",
    ),
    re_path(
        r"^issuers/(?P<entity_id>[^/]+)/badgeclasses$",
        IssuerBadgeClassList.as_view(),
        name="v2_api_issuer_badgeclass_list",
    ),
    re_path(
        r"^badgeclasses$", AllBadgeClassesList.as_view(), name="v2_api_badgeclass_list"
    ),
    re_path(
        r"^badgeclasses/changed$",
        BadgeClassesChangedSince.as_view(),
        name="v2_api_badgeclasses_changed_list",
    ),
    re_path(
        r"^badgeclasses/(?P<entity_id>[^/]+)$",
        BadgeClassDetail.as_view(),
        name="v2_api_badgeclass_detail",
    ),
    re_path(
        r"^badgeclasses/(?P<entity_id>[^/]+)/issue$",
        BatchAssertionsIssue.as_view(),
        name="v2_api_badgeclass_issue",
    ),
    re_path(
        r"^badgeclasses/(?P<entity_id>[^/]+)/assertions$",
        BadgeInstanceList.as_view(),
        name="v2_api_badgeclass_assertion_list",
    ),
    re_path(
        r"^assertions/revoke$",
        BatchAssertionsRevoke.as_view(),
        name="v2_api_assertion_revoke",
    ),
    re_path(
        r"^assertions/changed$",
        AssertionsChangedSince.as_view(),
        name="v2_api_assertions_changed_list",
    ),
    re_path(
        r"^assertions/(?P<entity_id>[^/]+)$",
        BadgeInstanceDetail.as_view(),
        name="v2_api_assertion_detail",
    ),
    re_path(r"^tokens/issuers$", IssuerTokensList.as_view(), name="v2_api_tokens_list"),
]
