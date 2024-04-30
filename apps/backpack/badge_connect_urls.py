# encoding: utf-8
from __future__ import unicode_literals

from backpack.badge_connect_api import (
    BadgeConnectAssertionListView,
    BadgeConnectProfileView,
)
from django.conf.urls import url

urlpatterns = [
    url(
        r"^assertions$",
        BadgeConnectAssertionListView.as_view(),
        name="bc_api_backpack_assertion_list",
    ),
    url(r"^profile$", BadgeConnectProfileView.as_view(), name="bc_api_profile"),
]
