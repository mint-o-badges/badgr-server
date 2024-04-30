from badgrsocialauth.api import (
    BadgrSocialAccountConnect,
    BadgrSocialAccountDetail,
    BadgrSocialAccountList,
)
from django.conf.urls import url

urlpatterns = [
    url(
        r"^socialaccounts$",
        BadgrSocialAccountList.as_view(),
        name="v2_api_user_socialaccount_list",
    ),
    url(
        r"^socialaccounts/connect$",
        BadgrSocialAccountConnect.as_view(),
        name="v2_api_user_socialaccount_connect",
    ),
    url(
        r"^socialaccounts/(?P<id>[^/]+)$",
        BadgrSocialAccountDetail.as_view(),
        name="v2_api_user_socialaccount_detail",
    ),
]
