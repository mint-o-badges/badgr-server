from django.urls import include, path

urlpatterns = []

urlpatterns.append(path("prometheus/", include("django_prometheus.urls")))
urlpatterns.append(path("", include("myapp.urls")))
