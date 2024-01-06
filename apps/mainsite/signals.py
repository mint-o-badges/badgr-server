from urllib.parse import urlparse

from django.apps import apps
from django.conf import settings

from mainsite.models import AccessTokenScope
from mainsite.utils import netloc_to_domain


CorsModel = apps.get_model(getattr(settings, 'BADGR_CORS_MODEL'))


def handle_token_save(sender, instance=None, **kwargs):
    for s in instance.scope.split():
        AccessTokenScope.objects.get_or_create(token=instance, scope=s)


def cors_allowed_sites(sender, request, **kwargs):
    origin = netloc_to_domain(urlparse(request.META['HTTP_ORIGIN']).netloc)
    return CorsModel.objects.filter(cors=origin).exists()
