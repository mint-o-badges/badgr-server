from django.conf.urls import url
from django.urls import include, path
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import routers

from . import api_v3

router = routers.DefaultRouter()
router.register(r'badges', api_v3.Badges, basename='badges')
router.register(r'learningpaths', api_v3.LearningPaths, basename='learningpaths')

urlpatterns = [
	path('', include(router.urls)),
]