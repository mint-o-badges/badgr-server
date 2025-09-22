from django.urls import include, path
from rest_framework import routers

from . import api_v3

router = routers.DefaultRouter()
router.register(r"preferences", api_v3.Preferences, basename="preferences")

urlpatterns = [
    path("", include(router.urls)),
]
