# encoding: utf-8


from django.urls import re_path

from badgeuser.api import (
    BadgeUserAccountConfirm,
    BadgeUserToken,
    BadgeUserForgotPassword,
    BadgeUserEmailConfirm,
    BadgeUserDetail,
    AccessTokenList,
    AccessTokenDetail,
    LatestTermsVersionDetail,
    ApplicationList,
    ApplicationDetails,
)

urlpatterns = [
    re_path(r"^auth/token$", BadgeUserToken.as_view(), name="v2_api_auth_token"),
    re_path(
        r"^auth/forgot-password$",
        BadgeUserForgotPassword.as_view(),
        name="v2_api_auth_forgot_password",
    ),
    re_path(
        r"^auth/confirm-email/(?P<confirm_id>[^/]+)$",
        BadgeUserEmailConfirm.as_view(),
        name="v2_api_auth_confirm_email",
    ),
    re_path(
        r"^auth/confirm-account/(?P<authcode>[^/]+)$",
        BadgeUserAccountConfirm.as_view(),
        name="v2_api_account_confirm",
    ),
    re_path(
        r"^auth/tokens$", AccessTokenList.as_view(), name="v2_api_access_token_list"
    ),
    re_path(
        r"^auth/tokens/(?P<entity_id>[^/]+)$",
        AccessTokenDetail.as_view(),
        name="v2_api_access_token_detail",
    ),
    re_path(
        r"^auth/applications$",
        ApplicationList.as_view(),
        name="v2_api_application_list",
    ),
    re_path(
        r"^auth/applications/(?P<application_id>[^/]+)$",
        ApplicationDetails.as_view(),
        name="v2_api_application_details",
    ),
    re_path(
        r"^users/(?P<entity_id>self)$",
        BadgeUserDetail.as_view(),
        name="v2_api_user_self",
    ),
    re_path(
        r"^users/(?P<entity_id>[^/]+)$",
        BadgeUserDetail.as_view(),
        name="v2_api_user_detail",
    ),
    re_path(
        r"^termsVersions/latest$",
        LatestTermsVersionDetail.as_view(),
        name="v2_latest_terms_version_detail",
    ),
]
