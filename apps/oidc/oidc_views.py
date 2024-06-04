from django.shortcuts import render
from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import permission_classes, authentication_classes, api_view

class OidcView():
    def login(request):
        return render(request, 'login.html')
    
    @api_view(['GET'])
    @authentication_classes([])
    @permission_classes([])
    def oidcLogoutRedirect(req):
        if req.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        # TODO: Currently the automatic logout / redirect doesn't work, since we
        # don't store the ID token long enough (since we log out the user from the django session
        # after they received the access token). We need to think about whether this
        # is worth the trade-off
        redirect_url = f"{settings.OIDC_OP_END_SESSION_ENDPOINT}?post_redirect_uri={settings.LOGOUT_REDIRECT_URL}&client_id={settings.OIDC_RP_CLIENT_ID}"
        return redirect(redirect_url)

