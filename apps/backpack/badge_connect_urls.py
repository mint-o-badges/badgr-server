# encoding: utf-8
from __future__ import unicode_literals

from django.conf.urls import url

from backpack.badge_connect_api import BadgeConnectProfileView, BadgeConnectAssertionListView

urlpatterns = [
    url(r'^assertions$', BadgeConnectAssertionListView.as_view(), name='bc_api_backpack_assertion_list'),
    url(r'^profile$', BadgeConnectProfileView.as_view(), name='bc_api_profile'),
]
