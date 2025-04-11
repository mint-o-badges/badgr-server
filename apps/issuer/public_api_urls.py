from django.conf.urls import url
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.urlpatterns import format_suffix_patterns

from .public_api import (IssuerJson, IssuerList, IssuerBadgesJson, IssuerLearningPathsJson, IssuerImage, BadgeClassJson, BadgeClassList,
                         BadgeClassImage, BadgeClassCriteria, BadgeInstanceJson, IssuerSearch, LearningPathJson,
                         BadgeInstanceImage, BackpackCollectionJson, BakedBadgeInstanceImage, LearningPathList,
                         OEmbedAPIEndpoint, VerifyBadgeAPIEndpoint, BadgeLearningPathList)

json_patterns = [
    url(r'^issuers/(?P<entity_id>[^/.]+)$',
        xframe_options_exempt(IssuerJson.as_view(slugToEntityIdRedirect=True)), name='issuer_json'),
    url(r'^issuers/search/(?P<searchterm>[^/]+)$',
        xframe_options_exempt(IssuerSearch.as_view()), 
    name='issuer_search'),
    url(r'^issuers/(?P<entity_id>[^/.]+)/badges$', xframe_options_exempt(
        IssuerBadgesJson.as_view(slugToEntityIdRedirect=True)), name='issuer_badges_json'),
    url(r'^issuers/(?P<entity_id>[^/.]+)/learningpaths$', xframe_options_exempt(
        IssuerLearningPathsJson.as_view(slugToEntityIdRedirect=True)), name='issuer_learningpaths_json'),    
    url(r'^all-issuers$', xframe_options_exempt(IssuerList.as_view()), name='issuer_list_json'),
    url(r'^badges/(?P<entity_id>[^/.]+)$',
        xframe_options_exempt(BadgeClassJson.as_view(slugToEntityIdRedirect=True)), name='badgeclass_json'),
    url(r'^badges/(?P<entity_id>[^/.]+)/learningpaths$',
        xframe_options_exempt(BadgeLearningPathList.as_view()), name='badge_learningpath_list_json'),    
    url(r'^learningpaths/(?P<entity_id>[^/.]+)$',
        xframe_options_exempt(LearningPathJson.as_view(slugToEntityIdRedirect=True)), name='learningpath_json'),    
    url(r'^all-badges$', xframe_options_exempt(BadgeClassList.as_view()), name='badgeclass_list_json'),
    url(r'^all-learningpaths$', xframe_options_exempt(LearningPathList.as_view()), name='learningpath_list_json'),
    url(r'^assertions/(?P<entity_id>[^/.]+)$', xframe_options_exempt(
        BadgeInstanceJson.as_view(slugToEntityIdRedirect=True)), name='badgeinstance_json'),

    url(r'^collections/(?P<entity_id>[^/.]+)$', xframe_options_exempt(
        BackpackCollectionJson.as_view(slugToEntityIdRedirect=True)), name='collection_json'),

    url(r'^oembed$', OEmbedAPIEndpoint.as_view(), name='oembed_api_endpoint'),

    url(r'^verify$', VerifyBadgeAPIEndpoint.as_view(), name='verify_badge_api_endpoint'),
]

image_patterns = [
    url(r'^issuers/(?P<entity_id>[^/]+)/image$', IssuerImage.as_view(slugToEntityIdRedirect=True), name='issuer_image'),
    url(r'^badges/(?P<entity_id>[^/]+)/image',
        BadgeClassImage.as_view(slugToEntityIdRedirect=True), name='badgeclass_image'),
    url(r'^badges/(?P<entity_id>[^/]+)/criteria',
        BadgeClassCriteria.as_view(slugToEntityIdRedirect=True), name='badgeclass_criteria'),
    url(r'^assertions/(?P<entity_id>[^/]+)/image',
        BadgeInstanceImage.as_view(slugToEntityIdRedirect=True), name='badgeinstance_image'),
    url(r'^assertions/(?P<entity_id>[^/]+)/baked',
        BakedBadgeInstanceImage.as_view(slugToEntityIdRedirect=True), name='badgeinstance_bakedimage'),
]

urlpatterns = format_suffix_patterns(json_patterns, allowed=['json']) + image_patterns
