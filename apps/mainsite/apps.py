from corsheaders.signals import check_request_enabled
from django.apps import AppConfig
from django.conf import settings


class BadgrConfig(AppConfig):
    name = "mainsite"

    def ready(self):
        # Makes sure all signal handlers are connected
        if getattr(settings, "BADGR_CORS_MODEL"):
            from mainsite.signals import cors_allowed_sites

            check_request_enabled.connect(cors_allowed_sites)
