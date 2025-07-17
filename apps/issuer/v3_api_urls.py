from django.urls import include, path
from rest_framework import routers

from . import api_v3

router = routers.DefaultRouter()
router.register(r"badges/tags", api_v3.BadgeTags, basename="badge-tags")
router.register(r"badges", api_v3.Badges, basename="badges")
router.register(r"issuers", api_v3.Issuers)
router.register(r"learningpaths", api_v3.LearningPaths)

urlpatterns = [
    path("", include(router.urls)),
]
