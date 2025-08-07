import json
from urllib.parse import urlparse

from django.conf import settings
from django.http import JsonResponse

from apps.mainsite.views import call_aiskills_api

# pulls esco competencies from badge assertions and enhances them with
# tree structure breadrcumbs using the AI Tool APIs
def get_skills_tree(badge_instances, language):
    skill_studyloads = {}
    for instance in badge_instances:
        if len(instance.badgeclass.cached_extensions()) > 0:
            for extension in instance.badgeclass.cached_extensions():
                if extension.name == "extensions:CompetencyExtension":
                    extension_json = json.loads(extension.original_json)
                    for competency in extension_json:
                        if competency["framework_identifier"]:
                            esco_uri = competency["framework_identifier"]
                            parsed_uri = urlparse(esco_uri)
                            uri_path = parsed_uri.path
                            studyload = competency["studyLoad"]
                            try:
                                skill_studyloads[uri_path] += studyload
                            except KeyError:
                                skill_studyloads[uri_path] = studyload

    if not len(skill_studyloads.keys()) > 0:
        return JsonResponse({"skills": []})

    # get esco trees from ai skills api
    endpoint = getattr(settings, "AISKILLS_ENDPOINT_TREE")
    payload = {"concept_uris": list(skill_studyloads.keys()), "lang": language}
    tree_json = call_aiskills_api(endpoint, "POST", payload)
    tree = json.loads(tree_json.content.decode())

    # extend with our studyloads
    for skill in tree["skills"]:
        skill["studyLoad"] = skill_studyloads[skill["concept_uri"]]

    return tree
