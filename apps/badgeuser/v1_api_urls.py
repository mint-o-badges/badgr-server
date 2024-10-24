from django.conf.urls import url

from badgeuser.api import (BadgeUserToken, BadgeUserForgotPassword, BadgeUserEmailConfirm, BadgeUserDetail, 
    BadgeUserResendEmailConfirmation, BadgeUserNewsletterOptIn, MarketingOptInConfirm, BadgeUserNewsletterConfirm,
    BadgeUserTosConfirm, BadgeUserNewsletterSubscription)
from badgeuser.api_v1 import BadgeUserEmailList, BadgeUserEmailDetail

urlpatterns = [
    url(r'^auth-token$', BadgeUserToken.as_view(), name='v1_api_user_auth_token'),
    url(r'^profile$', BadgeUserDetail.as_view(), name='v1_api_user_profile'),
    url(r'^forgot-password$', BadgeUserForgotPassword.as_view(), name='v1_api_auth_forgot_password'),
    url(r'^emails$', BadgeUserEmailList.as_view(), name='v1_api_user_emails'),
    url(r'^emails/(?P<id>[^/]+)$', BadgeUserEmailDetail.as_view(), name='v1_api_user_email_detail'),
    url(r'^legacyconfirmemail/(?P<confirm_id>[^/]+)$',
        BadgeUserEmailConfirm.as_view(), name='legacy_user_email_confirm'),
    url(r'^confirmemail/(?P<confirm_id>[^/]+)$', BadgeUserEmailConfirm.as_view(),
        name='v1_api_user_email_confirm'),
    url(r'^resendemail$', BadgeUserResendEmailConfirmation.as_view(), name='v1_api_resend_user_verification_email'),
    url(r'^confirm-newsletter$', BadgeUserNewsletterConfirm.as_view(), name='v1_api_user_newsletter_confirm'),
    url(r'^subscribe-newsletter$', BadgeUserNewsletterSubscription.as_view(), name='v1_api_user_newsletter_subscribe'),
    url(r'^confirm-tos$', BadgeUserTosConfirm.as_view(), name='v1_api_user_tos_confirm'),

]
