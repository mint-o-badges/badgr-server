import json

from allauth.account.admin import EmailAddress
from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from lti_tool.views import csrf_exempt

from badgeuser.models import BadgeUser
from backpack.utils import get_skills_tree
from mainsite.models import IframeUrl
from issuer.models import BadgeInstance


@xframe_options_exempt
@csrf_exempt
def iframe(request, *args, **kwargs):
    iframe_uuid = kwargs.get("iframe_uuid")
    try:
        iframe = IframeUrl.objects.get(id=iframe_uuid)
        # get from db and delete to create "single-use" urls
        # TODO: might be better to change to a time based solution,
        # cleanup of old entries will be needed either way
        iframe.delete()
    except IframeUrl.DoesNotExist:
        return HttpResponseNotFound()

    try:
        if iframe.name == "profile":
            return iframe_profile(
                request, iframe.params["skills"], iframe.params["language"]
            )
    except Exception as e:
        # show errors while debug
        if settings.DEBUG:
            raise e
        # else continue to 404
        pass

    return HttpResponseNotFound()


def iframe_profile(request, skills, language):
    skill_json = json.dumps(skills, ensure_ascii=False)
    return render(request, "lti/profile/index.html", context={"skill_json": skill_json})
