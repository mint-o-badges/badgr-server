from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)


class OidcView:
    @api_view(["GET"])
    @authentication_classes([])
    @permission_classes([])
    def oidcLogoutRedirect(req):
        if req.method != "GET":
            return JsonResponse(
                {"error": "Method not allowed"},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        # TODO: Currently the automatic logout / redirect doesn't work, since we
        # don't store the ID token long enough (since we log out the user from the django session
        # after they received the access token). We need to think about whether this
        # is worth the trade-off
        redirect_url = (
            f"{settings.OIDC_OP_END_SESSION_ENDPOINT}"
            f"?post_redirect_uri={settings.LOGOUT_REDIRECT_URL}"
            f"&client_id={settings.OIDC_RP_CLIENT_ID}"
        )
        return redirect(redirect_url)
