import json
from django.shortcuts import render
from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpRequest, JsonResponse

import jwt
from rest_framework import status
from rest_framework.decorators import permission_classes, authentication_classes, api_view

from oauth2_provider.models import RefreshToken, AccessToken
from mainsite.models import AccessTokenSessionId

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

    @api_view(['POST'])
    @authentication_classes([])
    @permission_classes([])
    def oidcTriggerLogout(req: HttpRequest):
        # TODO: If there is some method of further validating that this is a legitimate
        # logout request, we should implement it
        if req.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        body = json.loads(req.body.decode('utf-8'))
        if not hasattr(body, 'content'):
            return JsonResponse({"error": "Expected content in body"}, status=status.HTTP_400_BAD_REQUEST)
        
        content = body.content
        if not hasattr(content, 'LOGOUT_TOKEN'):
            # TODO: The logout token might be stored under a different name
            return JsonResponse({"error": "Expected LOGOUT_TOKEN in body content"}, status=status.HTTP_400_BAD_REQUEST)

        decoded_token = jwt.decode(content.LOGOUT_TOKEN, options={"verify_signature": False})
        if not hasattr(decoded_token, 'sid'):
            return JsonResponse({"error": "Expected logout token to contain session ID (sid)"}, status=status.HTTP_400_BAD_REQUEST)

        session_id = decoded_token['sid']
        if not AccessToken.objects.contains(sessionId=session_id):
            return JsonResponse({"error": "Didn't find any access token related to the specified session ID"}, status=status.HTTP_404_NOT_FOUND)
        
        access_token = AccessToken.objects.get(sessionId=session_id)
        if not RefreshToken.objects.contains(access_token=access_token):
            return JsonResponse({"error": "Didn't find any refresh token related to the specified access token"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        refresh_token = RefreshToken.objects.get(access_token=access_token)

        # This also revokes the associated access token
        refresh_token.revoke()
        return JsonResponse({"success": "Successfully revoked token(s)"}, status=status.HTTP_200_OK)
