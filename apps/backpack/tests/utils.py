import os

import responses

CURRENT_DIRECTORY = os.path.dirname(__file__)


def setup_basic_1_0(**kwargs):
    if not kwargs or "http://a.com/instance" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/instance",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_instance.json"),
                "r",
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/badgeclass" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/badgeclass",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_badgeclass.json"),
                "r",
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/issuer" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/issuer",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_issuer.json"), "r"
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/badgeclass_image" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/badgeclass_image",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/unbaked_image.png"), "rb"
            ).read(),
            status=200,
            content_type="image/png",
        )


def setup_basic_1_0_bad_image(**kwargs):
    if not kwargs or "http://a.com/instance" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/instance",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_instance.json"),
                "r",
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/badgeclass" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/badgeclass",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_badgeclass.json"),
                "r",
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/issuer" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/issuer",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/1_0_basic_issuer.json"), "r"
            ).read(),
            status=200,
            content_type="application/json",
        )
    if not kwargs or "http://a.com/badgeclass_image" not in kwargs.get("exclude", []):
        responses.add(
            responses.GET,
            "http://a.com/badgeclass_image",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/bad_image.png"), "rb"
            ).read(),
            status=200,
            content_type="image/png",
        )


def setup_resources(resources):
    for item in resources:
        response_body = item.get("response_body")
        if response_body is None:
            mode = item["mode"] if "mode" in item else "r"
            response_body = open(
                os.path.join(CURRENT_DIRECTORY, "testfiles", item["filename"]), mode
            ).read()
        responses.add(
            responses.GET,
            item["url"],
            body=response_body,
            status=item.get("status", 200),
            content_type=item.get("content_type", "application/json"),
        )


def setup_basic_0_5_0(**kwargs):
    responses.add(
        responses.GET,
        "http://oldstyle.com/instance",
        body=open(
            os.path.join(CURRENT_DIRECTORY, "testfiles/0_5_basic_instance.json"), "r"
        ).read(),
        status=200,
        content_type="application/json",
    )
    if not kwargs or "http://oldstyle.com/images/1" not in kwargs.get("exclude"):
        responses.add(
            responses.GET,
            "http://oldstyle.com/images/1",
            body=open(
                os.path.join(CURRENT_DIRECTORY, "testfiles/unbaked_image.png"), "rb"
            ).read(),
            status=200,
            content_type="image/png",
        )
