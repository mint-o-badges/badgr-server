from django.conf.urls import url

from badgeuser.api import BadgeRequestVerification, BadgeUserSaveMicroDegree, BadgeUserToken, BadgeUserForgotPassword, BadgeUserEmailConfirm, BadgeUserDetail, BadgeUserResendEmailConfirmation, LearningPathList
from badgeuser.api_v1 import BadgeUserEmailList, BadgeUserEmailDetail

urlpatterns = [
    url(r'^auth-token$', BadgeUserToken.as_view(), name='v1_api_user_auth_token'),
    url(r'^profile$', BadgeUserDetail.as_view(), name='v1_api_user_profile'),
    url(r'^forgot-password$', BadgeUserForgotPassword.as_view(), name='v1_api_auth_forgot_password'),
    url(r'^badge-request/verify$', BadgeRequestVerification.as_view(), name='v1_api_badge_request_verification'),
    url(r'^emails$', BadgeUserEmailList.as_view(), name='v1_api_user_emails'),
    url(r'^emails/(?P<id>[^/]+)$', BadgeUserEmailDetail.as_view(), name='v1_api_user_email_detail'),
    url(r'^legacyconfirmemail/(?P<confirm_id>[^/]+)$',
        BadgeUserEmailConfirm.as_view(), name='legacy_user_email_confirm'),
    url(r'^confirmemail/(?P<confirm_id>[^/]+)$', BadgeUserEmailConfirm.as_view(),
        name='v1_api_user_email_confirm'),    
    url(r'^resendemail$', BadgeUserResendEmailConfirmation.as_view(), name='v1_api_resend_user_verification_email'),
    url(r'^learningpaths$', LearningPathList.as_view(), name='v1_api_user_learningpaths'),

    url(r'^save-microdegree/(?P<entity_id>[^/]+)$', BadgeUserSaveMicroDegree.as_view(),
        name='v1_api_user_save_microdegree'),
]
