from badgeuser.api import (
    BadgeRequestVerification,
    BadgeUserCollectBadgesInBackpack,
    BadgeUserConfirmStaffRequest,
    BadgeUserDetail,
    BadgeUserEmailConfirm,
    BadgeUserForgotPassword,
    BadgeUserResendEmailConfirmation,
    BadgeUserSaveMicroDegree,
    BadgeUserToken,
    GetRedirectPath,
    IssuerStaffRequestDetail,
    IssuerStaffRequestList,
    LearningPathList,
)
from badgeuser.api_v1 import BadgeUserEmailDetail, BadgeUserEmailList
from django.conf.urls import url

urlpatterns = [
    url(r"^auth-token$", BadgeUserToken.as_view(), name="v1_api_user_auth_token"),
    url(r"^profile$", BadgeUserDetail.as_view(), name="v1_api_user_profile"),
    url(
        r"^forgot-password$",
        BadgeUserForgotPassword.as_view(),
        name="v1_api_auth_forgot_password",
    ),
    url(
        r"^badge-request/verify$",
        BadgeRequestVerification.as_view(),
        name="v1_api_badge_request_verification",
    ),
    url(r"^emails$", BadgeUserEmailList.as_view(), name="v1_api_user_emails"),
    url(
        r"^emails/(?P<id>[^/]+)$",
        BadgeUserEmailDetail.as_view(),
        name="v1_api_user_email_detail",
    ),
    url(
        r"^legacyconfirmemail/(?P<confirm_id>[^/]+)$",
        BadgeUserEmailConfirm.as_view(),
        name="legacy_user_email_confirm",
    ),
    url(
        r"^confirmemail/(?P<confirm_id>[^/]+)$",
        BadgeUserEmailConfirm.as_view(),
        name="v1_api_user_email_confirm",
    ),
    url(
        r"^resendemail$",
        BadgeUserResendEmailConfirmation.as_view(),
        name="v1_api_resend_user_verification_email",
    ),
    url(
        r"^learningpaths$", LearningPathList.as_view(), name="v1_api_user_learningpaths"
    ),
    url(
        r"^save-microdegree/(?P<entity_id>[^/]+)$",
        BadgeUserSaveMicroDegree.as_view(),
        name="v1_api_user_save_microdegree",
    ),
    url(
        r"^collect-badges-in-backpack$",
        BadgeUserCollectBadgesInBackpack.as_view(),
        name="v1_api_user_collect_badges_in_backpack",
    ),
    url(
        r"^get-redirect-path$",
        GetRedirectPath.as_view(),
        name="v1_api_user_get_redirect_path",
    ),
    url(
        r"^issuerStaffRequests$",
        IssuerStaffRequestList.as_view(),
        name="v1_api_user_issuer_staff_requests",
    ),
    url(
        r"^issuerStaffRequest/issuer/(?P<issuer_id>[^/]+)$",
        IssuerStaffRequestDetail.as_view(),
        name="v1_api_user_issuer_staff_request_detail",
    ),
    url(
        r"^issuerStaffRequest/request/(?P<request_id>[^/]+)$",
        IssuerStaffRequestDetail.as_view(),
        name="v1_api_user_issuer_staff__revoke_request_detail",
    ),
    url(
        r"^confirm-staff-request/(?P<entity_id>[^/]+)$",
        BadgeUserConfirmStaffRequest.as_view(),
        name="v1_api_user_confirm_staffrequest",
    ),
]
