from django.urls import re_path

from badgrsocialauth.api import (
    BadgrSocialAccountList,
    BadgrSocialAccountDetail,
    BadgrSocialAccountConnect,
)

urlpatterns = [
    re_path(
        r"^socialaccounts$",
        BadgrSocialAccountList.as_view(),
        name="v1_api_user_socialaccount_list",
    ),
    re_path(
        r"^socialaccounts/connect$",
        BadgrSocialAccountConnect.as_view(),
        name="v1_api_user_socialaccount_connect",
    ),
    re_path(
        r"^socialaccounts/(?P<id>[^/]+)$",
        BadgrSocialAccountDetail.as_view(),
        name="v1_api_user_socialaccount_detail",
    ),
]
