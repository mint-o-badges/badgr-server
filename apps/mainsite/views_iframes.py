import json

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
        if iframe.iframe == "profile":
            user = BadgeUser.objects.get(pk=iframe.params["user"])
            return iframe_profile(request, user, iframe.params["language"])
    except:
        # on error 404
        pass

    return HttpResponseNotFound()

def iframe_profile(request, user, language):#

    instances = BadgeInstance.objects.filter(user=user)
    tree = get_skills_tree(instances, language)

    skill_json = json.dumps(tree['skills'], ensure_ascii=False)

    return render(request, "lti/profile/index.html", context={
        "skill_json": skill_json
    })
