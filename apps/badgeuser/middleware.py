from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import deprecation


class InactiveUserMiddleware(deprecation.MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, "user"):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the InactiveAccountMiddleware class."
            )
        if (
            request.user.is_authenticated
            and not request.user.is_active
            and request.path != reverse("account_enabled")
        ):
            return HttpResponseRedirect(reverse("account_enabled"))
