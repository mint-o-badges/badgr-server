import base64
import json
import time
import re
import os

from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.db import IntegrityError
from django.http import (
    HttpResponseServerError,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import FormView, RedirectView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import (
    permission_classes,
    authentication_classes,
    api_view,
)
from rest_framework.authentication import (
    SessionAuthentication,
    BasicAuthentication,
    TokenAuthentication,
)

from issuer.tasks import rebake_all_assertions, update_issuedon_all_assertions
from mainsite.admin_actions import clear_cache
from mainsite.models import EmailBlacklist, BadgrApp
from mainsite.serializers import LegacyVerifiedAuthTokenSerializer
from mainsite.utils import createHash, createHmac
from random import randrange
import badgrlog

from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import DefaultStorage

import uuid
from django.http import JsonResponse
import requests
from requests_oauthlib import OAuth1

logger = badgrlog.BadgrLogger()


##
#
#  Error Handler Views
#
##
@xframe_options_exempt
def error404(request, *args, **kwargs):
    try:
        template = loader.get_template("error/404.html")
    except TemplateDoesNotExist:
        return HttpResponseServerError(
            "<h1>Page not found (404)</h1>", content_type="text/html"
        )
    return HttpResponseNotFound(
        template.render(
            {
                "STATIC_URL": getattr(settings, "STATIC_URL", "/static/"),
            }
        )
    )


@xframe_options_exempt
def error500(request, *args, **kwargs):
    try:
        template = loader.get_template("error/500.html")
    except TemplateDoesNotExist:
        return HttpResponseServerError(
            "<h1>Server Error (500)</h1>", content_type="text/html"
        )
    return HttpResponseServerError(
        template.render(
            {
                "STATIC_URL": getattr(settings, "STATIC_URL", "/static/"),
            }
        )
    )


def info_view(request, *args, **kwargs):
    return redirect(getattr(settings, "LOGIN_REDIRECT_URL"))


# TODO: It is possible to call this method without authentication, thus storing files on the server
@csrf_exempt
def upload(req):
    if req.method == "POST":
        uploaded_file = req.FILES["files"]
        file_extension = uploaded_file.name.split(".")[-1]
        random_filename = str(uuid.uuid4())
        final_filename = random_filename + "." + file_extension
        store = DefaultStorage()
        store.save(final_filename, uploaded_file)
    return JsonResponse({"filename": final_filename})


@api_view(["GET"])
@authentication_classes(
    [TokenAuthentication, SessionAuthentication, BasicAuthentication]
)
@permission_classes([IsAuthenticated])
def aiskills(req, searchterm):
    # The searchterm is encoded URL safe, meaning that + and / got replaced by - and _
    searchterm = searchterm.replace("-", "+").replace("_", "/")
    searchterm = base64.b64decode(searchterm).decode("utf-8")
    if req.method != "GET":
        return JsonResponse(
            {"error": "Method not allowed"}, status=status.HTTP_400_BAD_REQUEST
        )

    attempt_num = 0  # keep track of how many times we've retried
    while attempt_num < 4:
        apiKey = getattr(settings, "AISKILLS_API_KEY")
        endpoint = getattr(settings, "AISKILLS_ENDPOINT")
        params = {"api_key": apiKey}
        payload = {"text_to_analyze": searchterm}
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        response = requests.post(
            endpoint, params=params, data=json.dumps(payload), headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data, status=status.HTTP_200_OK)
        elif response.status_code == 403 or response.status_code == 401:
            # Probably the API KEY was wrong
            return JsonResponse(
                {"error": "Couldn't authenticate against AI skills service!"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        elif response.status_code == 400:
            # Invalid input
            return JsonResponse(
                {"error": "Invalid searchterm!"}, status=status.HTTP_400_BAD_REQUEST
            )
        elif response.status_code == 500:
            # This is, weirdly enough, typically also an indication of an invalid searchterm
            return JsonResponse(
                {"error": extractErrorMessage500(response)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            attempt_num += 1
            # You can probably use a logger to log the error here
            time.sleep(5)  # Wait for 5 seconds before re-trying

    return JsonResponse(
        {"error": f"Request failed with status code {response.status_code}"},
        status=response.status_code,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def createCaptchaChallenge(req):
    if req.method != "GET":
        return JsonResponse(
            {"error": "Method not allowed"}, status=status.HTTP_400_BAD_REQUEST
        )

    hmac_secret = getattr(settings, "ALTCHA_SECRET")

    salt = os.urandom(12).hex()
    number = randrange(10000, 100000, 1)
    challenge = createHash(salt, number)
    signature = createHmac(hmac_secret, challenge)

    ch = {
        "algorithm": "SHA-256",
        "challenge": challenge,
        "salt": salt,
        "signature": signature,
    }

    return JsonResponse(ch)


def extractErrorMessage500(response: Response):
    expression = re.compile("<pre>Error: ([^<]+)<br>")
    match = expression.search(response.text)
    return match.group(1) if match else "Invalid searchterm! (Unknown error)"


@api_view(["GET"])
@authentication_classes(
    [TokenAuthentication, SessionAuthentication, BasicAuthentication]
)
@permission_classes([IsAuthenticated])
def nounproject(req, searchterm, page):
    if req.method == "GET":
        attempt_num = 0  # keep track of how many times we've retried
        while attempt_num < 4:
            auth = OAuth1(
                getattr(settings, "NOUNPROJECT_API_KEY"),
                getattr(settings, "NOUNPROJECT_SECRET"),
            )
            endpoint = (
                "http://api.thenounproject.com/v2/icon?query="
                + searchterm
                + "&limit=10&page="
                + page
            )
            response = requests.get(endpoint, auth=auth)
            if response.status_code == 200:
                data = response.json()
                return JsonResponse(data, status=status.HTTP_200_OK)
            elif response.status_code == 403:
                # Probably the API KEY / SECRET was wrong
                return JsonResponse(
                    {"error": "Couldn't authenticate against thenounproject!"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                attempt_num += 1
                # You can probably use a logger to log the error here
                time.sleep(5)  # Wait for 5 seconds before re-trying

        return JsonResponse(
            {"error": f"Request failed with status code {response.status_code}"},
            status=response.status_code,
        )
    else:
        return JsonResponse(
            {"error": "Method not allowed"}, status=status.HTTP_400_BAD_REQUEST
        )


def email_unsubscribe_response(request, message, error=False):
    badgr_app_pk = request.GET.get("a", None)

    badgr_app = BadgrApp.objects.get_by_id_or_default(badgr_app_pk)

    query_param = "infoMessage" if error else "authError"
    redirect_url = "{url}?{query_param}={message}".format(
        url=badgr_app.ui_login_redirect, query_param=query_param, message=message
    )
    return HttpResponseRedirect(redirect_to=redirect_url)


def email_unsubscribe(request, *args, **kwargs):
    if time.time() > int(kwargs["expiration"]):
        return email_unsubscribe_response(
            request, "Your unsubscription link has expired.", error=True
        )

    try:
        email = base64.b64decode(kwargs["email_encoded"]).decode("utf-8")
    except TypeError:
        logger.event(
            badgrlog.BlacklistUnsubscribeInvalidLinkEvent(kwargs["email_encoded"])
        )
        return email_unsubscribe_response(
            request, "Invalid unsubscribe link.", error=True
        )

    if not EmailBlacklist.verify_email_signature(**kwargs):
        logger.event(badgrlog.BlacklistUnsubscribeInvalidLinkEvent(email))
        return email_unsubscribe_response(
            request, "Invalid unsubscribe link.", error=True
        )

    blacklist_instance = EmailBlacklist(email=email)
    try:
        blacklist_instance.save()
        logger.event(badgrlog.BlacklistUnsubscribeRequestSuccessEvent(email))
    except IntegrityError:
        pass
    except Exception:
        logger.event(badgrlog.BlacklistUnsubscribeRequestFailedEvent(email))
        return email_unsubscribe_response(
            request, "Failed to unsubscribe email.", error=True
        )

    return email_unsubscribe_response(
        request,
        "You will no longer receive email notifications for earned"
        " badges from this domain.",
    )


class AppleAppSiteAssociation(APIView):
    renderer_classes = (JSONRenderer,)
    permission_classes = (AllowAny,)

    def get(self, request):
        data = {"applinks": {"apps": [], "details": []}}

        for app_id in getattr(settings, "APPLE_APP_IDS", []):
            data["applinks"]["details"].append(app_id)

        return Response(data=data)


class LegacyLoginAndObtainAuthToken(ObtainAuthToken):
    serializer_class = LegacyVerifiedAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        response = super(LegacyLoginAndObtainAuthToken, self).post(
            request, *args, **kwargs
        )
        response.data["warning"] = (
            "This method of obtaining a token is deprecated and will be removed. "
            "This request has been logged."
        )
        return response


class SitewideActionForm(forms.Form):
    ACTION_CLEAR_CACHE = "CLEAR_CACHE"
    ACTION_REBAKE_ALL_ASSERTIONS = "REBAKE_ALL_ASSERTIONS"
    ACTION_FIX_ISSUEDON = "FIX_ISSUEDON"

    ACTIONS = {
        ACTION_CLEAR_CACHE: clear_cache,
        ACTION_REBAKE_ALL_ASSERTIONS: rebake_all_assertions,
        ACTION_FIX_ISSUEDON: update_issuedon_all_assertions,
    }
    CHOICES = (
        (
            ACTION_CLEAR_CACHE,
            "Clear Cache",
        ),
        (
            ACTION_REBAKE_ALL_ASSERTIONS,
            "Rebake all assertions",
        ),
        (
            ACTION_FIX_ISSUEDON,
            "Re-process issuedOn for backpack assertions",
        ),
    )

    action = forms.ChoiceField(choices=CHOICES, required=True, label="Pick an action")
    confirmed = forms.BooleanField(
        required=True, label="Are you sure you want to perform this action?"
    )


class SitewideActionFormView(FormView):
    form_class = SitewideActionForm
    template_name = "admin/sitewide_actions.html"
    success_url = reverse_lazy("admin:index")

    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super(SitewideActionFormView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        action = form.ACTIONS[form.cleaned_data["action"]]

        if hasattr(action, "delay"):
            action.delay()
        else:
            action()

        return super(SitewideActionFormView, self).form_valid(form)


class RedirectToUiLogin(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        badgrapp = BadgrApp.objects.get_current()
        return (
            badgrapp.ui_login_redirect
            if badgrapp.ui_login_redirect is not None
            else badgrapp.email_confirmation_redirect
        )


class DocsAuthorizeRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        badgrapp = BadgrApp.objects.get_current(request=self.request)
        url = badgrapp.oauth_authorization_redirect
        if not url:
            url = "https://{cors}/auth/oauth2/authorize".format(cors=badgrapp.cors)

        query = self.request.META.get("QUERY_STRING", "")
        if query:
            url = "{}?{}".format(url, query)
        return url
