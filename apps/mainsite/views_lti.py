from typing import Literal
from django.conf import settings
from django.http import (
    HttpResponseNotFound,
)
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from oauthlib.oauth2.rfc6749.tokens import random_token_generator
from oauth2_provider.models import AccessToken

from allauth.account.models import EmailAddress
from lti_tool.views import LtiLaunchBaseView, OIDCLoginInitView
from lti_tool.models import LtiUser, LtiLaunch
from pylti1p3.deep_link_resource import DeepLinkResource

from apps.backpack.api import BackpackAssertionList
from apps.badgeuser.api import BadgeUserDetail
from apps.mainsite.admin import Application
from backpack.utils import get_skills_tree
from issuer.models import BadgeInstance, Issuer, LearningPath, LearningPathBadge
from mainsite.views_iframes import (
    iframe_backpack,
    iframe_badge_create_or_edit,
    iframe_badges,
    iframe_competencies,
    iframe_learningpaths,
    iframe_profile,
)

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

        # if we don't set a custom parameter moodle throws an error
        lti_profile = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/profile/")
            .set_custom_params({"custom": ""})
            .set_title("Learners Profile")
        )
        lti_badges = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/badges/")
            .set_custom_params({"custom": ""})
            .set_title("Earned Badges")
        )
        lti_competencies = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/competencies/")
            .set_custom_params({"custom": ""})
            .set_title("Learners Competencies")
        )
        lti_learningpaths = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/learningpaths/")
            .set_custom_params({"custom": ""})
            .set_title("Learners Learnings Paths")
        )
        lti_backpack = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/backpack/")
            .set_custom_params({"custom": ""})
            .set_title("Learners Backpack")
        )
        lti_badge_create_or_edit = (
            DeepLinkResource()
            .set_url(f"{baseUrl}/lti/tools/badge-create-or-edit")
            .set_custom_params({"custom": ""})
            .set_title("Create or edit a badge"),
        )

        resources = [
            lti_profile,
            lti_badges,
            lti_competencies,
            lti_learningpaths,
            lti_backpack,
            lti_badge_create_or_edit,
        ]
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
    # else get badgeinstances by the recipient (when the user is not registered)
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
    except EmailAddress.DoesNotExist:
        instances = BadgeInstance.objects.filter(recipient_identifier=lti_user.email)

    tree = get_skills_tree(instances, locale)

    return iframe_profile(request, tree["skills"], locale)


@xframe_options_exempt
@csrf_exempt
def LtiBadges(request):
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
    # else get badgeinstances by the recipient (when the user is not registered)
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
    except EmailAddress.DoesNotExist:
        instances = BadgeInstance.objects.filter(recipient_identifier=lti_user.email)

    return iframe_badges(
        request,
        BackpackAssertionList.v1_serializer_class().to_representation(instances),
        locale,
    )


@xframe_options_exempt
@csrf_exempt
def LtiCompetencies(request):
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
    # else get badgeinstances by the recipient (when the user is not registered)
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
    except EmailAddress.DoesNotExist:
        instances = BadgeInstance.objects.filter(recipient_identifier=lti_user.email)

    return iframe_competencies(
        request,
        BackpackAssertionList.v1_serializer_class().to_representation(instances),
        locale,
    )


@xframe_options_exempt
@csrf_exempt
def LtiLearningpaths(request):
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
    # else get badgeinstances by the recipient (when the user is not registered)
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
        badges = list(
            {
                badgeinstance.badgeclass
                for badgeinstance in instances
                if badgeinstance.revoked is False
            }
        )
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(
            activated=True, learningpathbadge__in=lp_badges
        ).distinct()

        return iframe_learningpaths(
            request,
            lps,
            locale,
        )
    except EmailAddress.DoesNotExist:
        return render(request, "lti/not_logged_in.html")


@xframe_options_exempt
@csrf_exempt
def LtiBackpack(request):
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
    # else get badgeinstances by the recipient (when the user is not registered)
    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
        instances = BadgeInstance.objects.filter(user=badgeuser)
        badges = list(
            {
                badgeinstance.badgeclass
                for badgeinstance in instances
                if badgeinstance.revoked is False
            }
        )
        lp_badges = LearningPathBadge.objects.filter(badge__in=badges)
        lps = LearningPath.objects.filter(
            activated=True, learningpathbadge__in=lp_badges
        ).distinct()
        tree = get_skills_tree(instances, locale)

        profile = BadgeUserDetail.v1_serializer_class().to_representation(badgeuser)

        return iframe_backpack(
            request,
            profile,
            tree["skills"],
            BackpackAssertionList.v1_serializer_class().to_representation(instances),
            lps,
            locale,
        )
    except EmailAddress.DoesNotExist:
        return render(request, "lti/not_logged_in.html")


@xframe_options_exempt
@csrf_exempt
def LtiBadgeCreateOrEdit(request):
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

    try:
        email_variant = EmailAddress.objects.get(email__iexact=lti_user.email)
        badgeuser = email_variant.user
    except EmailAddress.DoesNotExist:
        return render(request, "lti/user_not_found.html")

    locale = get_lang_for_lti_launch(request.lti_launch)

    # if the user is only in one issuer organization
    # we may as well already hand that to the iframe.
    # We let the client handle when the user isn't
    # staff of any issuer.
    issuers = Issuer.objects.filter(staff__id=badgeuser.id).distinct()
    issuer = None
    if issuers.count() == 1:
        issuer = issuers.first()

    if request.auth:
        application = request.auth.application
    else:
        # use public oauth app if not token auth
        application = Application.objects.get(client_type="public")

    token = AccessToken.objects.create(
        user=request.user,
        application=application,
        token=random_token_generator(request, False),
        scope="rw:issuer rw:profile",
        expires=(timezone.now() + timezone.timedelta(0, 3600)),
    )

    return iframe_badge_create_or_edit(request, token.token, None, issuer, locale, True)


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
