# encoding: utf-8
from __future__ import unicode_literals

from django.urls import re_path

from backpack.badge_connect_api import (
    BadgeConnectProfileView,
    BadgeConnectAssertionListView,
)

urlpatterns = [
    re_path(
        r"^assertions$",
        BadgeConnectAssertionListView.as_view(),
        name="bc_api_backpack_assertion_list",
    ),
    re_path(r"^profile$", BadgeConnectProfileView.as_view(), name="bc_api_profile"),
]
