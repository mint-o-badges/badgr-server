from typing import Literal
from django.conf import settings
from django.http import (
    HttpResponseNotFound,
)
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from allauth.account.models import EmailAddress
from lti_tool.views import LtiLaunchBaseView, OIDCLoginInitView
from lti_tool.models import LtiUser, LtiLaunch
from pylti1p3.deep_link_resource import DeepLinkResource

from backpack.utils import get_skills_tree
from issuer.models import BadgeInstance
from mainsite.views_iframes import iframe_profile

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = Literal["en", "de"]


@method_decorator(xframe_options_exempt, name="dispatch")
class XFrameExemptOIDCLoginInitView(OIDCLoginInitView):
    pass


@method_decorator(xframe_options_exempt, name="dispatch")
class ApplicationLaunchView(LtiLaunchBaseView):
    def launch_setup(self, request, lti_launch):
        # activate automatically created deployments
        if not lti_launch.deployment.is_active:
            lti_launch.deployment.is_active = True
            lti_launch.deployment.save()

    def handle_resource_launch(self, request, lti_launch):
        # django-lti recommends to redirect to the proper tool for some reason,
        # but we might as well just call it directly so the lti_launch context
        # is kept. When redirecting we would need to save lti_launch.user
        # information in a session variable
        return LtiProfile(request)

    def handle_deep_linking_launch(self, request, lti_launch):
        baseUrl = getattr(settings, "HTTP_ORIGIN", "http://localhost:8000")
        resources = []
        resources.append(
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/profile/")
            # if we don't set a custom parameter moodle throws an error
            .set_custom_params({"custom": ""})
            .set_title("Learners Profile")
        )
        return lti_launch.deep_link_response(resources)


@xframe_options_exempt
@csrf_exempt
def LtiProfile(request):
    if not request.lti_launch.is_present:
        return HttpResponseNotFound(
            "Error: no LTI context".encode(), content_type="text/html"
        )

    # check if the embedding tool provided an email adress
    lti_user = request.lti_launch.user
    try:
        if not lti_user.email:
            raise LtiUser.DoesNotExist
    except LtiUser.DoesNotExist:
        return render(request, "lti/not_logged_in.html")

    locale = get_lang_for_lti_launch(request.lti_launch)

    # try to find a badgeuser by email and get his badgeinstances,
    # else get badgeinstances by
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
    except EmailAddress.DoesNotExist:
        instances = BadgeInstance.objects.filter(recipient_identifier=lti_user.email)

    tree = get_skills_tree(instances, locale)

    return iframe_profile(request, tree["skills"], locale)


def get_lang_for_lti_launch(lti_launch: LtiLaunch) -> SUPPORTED_LOCALES:
    # get language (locale) from lti_launch data
    launch_data = lti_launch.get_launch_data()
    if not launch_data:
        return DEFAULT_LOCALE

    launch_presentation = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/launch_presentation", {}
    )
    locale = launch_presentation.get("locale", DEFAULT_LOCALE).lower()
    if locale not in SUPPORTED_LOCALES:
        return DEFAULT_LOCALE
    else:
        return locale
