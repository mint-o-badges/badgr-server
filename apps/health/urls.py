from django.urls import re_path

from .views import health

urlpatterns = [
    re_path(r"^$", health, name="server_health"),
]
