# encoding: utf-8
"""
Dashboard URL Configuration
"""
from django.conf.urls import url
from .api import (
    DashboardKPIsView,
    CompetencyAreasListView,
    CompetencyAreaDetailView,
    TopBadgesView,
)

urlpatterns = [
    # KPIs endpoint
    url(
        r'^kpis/?$',
        DashboardKPIsView.as_view(),
        name='dashboard_kpis'
    ),

    # Competency areas endpoints
    url(
        r'^competency-areas/?$',
        CompetencyAreasListView.as_view(),
        name='dashboard_competency_areas_list'
    ),
    url(
        r'^competency-areas/(?P<area_id>[^/]+)/?$',
        CompetencyAreaDetailView.as_view(),
        name='dashboard_competency_area_detail'
    ),

    # Top badges endpoint
    url(
        r'^top-badges/?$',
        TopBadgesView.as_view(),
        name='dashboard_top_badges'
    ),
]
