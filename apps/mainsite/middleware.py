from django import http
from django.utils import deprecation
from django.utils.deprecation import MiddlewareMixin
from mainsite import settings
from django.conf import settings as django_settings
import logging

logger = logging.getLogger("Badgr.Events")


class MaintenanceMiddleware(deprecation.MiddlewareMixin):
    """Serve a temporary redirect to a maintenance url in maintenance mode"""

    def process_request(self, request):
        if request.method == "POST":
            if getattr(settings, "MAINTENANCE_MODE", False) is True and hasattr(
                settings, "MAINTENANCE_URL"
            ):
                return http.HttpResponseRedirect(settings.MAINTENANCE_URL)
            return None


class TrailingSlashMiddleware(deprecation.MiddlewareMixin):
    def process_request(self, request):
        """Removes the slash from urls, or adds a slash for the admin urls"""
        exceptions = ["/staff", "/__debug__"]
        if list(filter(request.path.startswith, exceptions)):
            if request.path[-1] != "/":
                return http.HttpResponsePermanentRedirect(request.path + "/")
        else:
            if request.path != "/" and request.path[-1] == "/":
                return http.HttpResponsePermanentRedirect(request.path[:-1])
        return None


class XframeExempt500Middleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code == 500:
            response.xframe_options_exempt = True
        return response

class ExceptionLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if django_settings.DEBUG:
            return None
        logger.error("An unhandled exception occurred:")
        logger.exception(exception)

class CookieToBearerMiddleware(MiddlewareMixin):
    """
    Makes sure that tokens passed as cookie are added as
    bearer HTTP_AUTHORIZATION, so that oauth2_provider can
    handle them
    """

    def process_request(self, request):
        # do something only if request contains access token cookie
        if "access_token" in request.COOKIES:
            request.META["HTTP_AUTHORIZATION"] = (
                f"Bearer {request.COOKIES['access_token']}"
            )
