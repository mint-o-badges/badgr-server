from django.conf.urls import url
from django.urls import include, path
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import routers

from . import api_v3

router = routers.DefaultRouter()
router.register(r'badge', api_v3.Badges)
router.register(r'issuer', api_v3.Issuers)
router.register(r'learningpath', api_v3.LearningPaths)

urlpatterns = [
	path('', include(router.urls)),
]