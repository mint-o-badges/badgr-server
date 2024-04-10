from django.conf.urls import re_path as url

from .views import health

urlpatterns = [
    url(r'^$', health, name='server_health'),
]
