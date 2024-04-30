# encoding: utf-8
import os

import badgrlog
import dateutil
import requests  # noqa: F401
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models.signals import post_save
from issuer.helpers import BadgeCheckHelper
from issuer.managers import resolve_source_url_referencing_local_object
from issuer.models import BadgeClass, BadgeInstance, Issuer
from issuer.utils import CURRENT_OBI_VERSION
from mainsite.celery import app
from mainsite.utils import convert_svg_to_png, verify_svg
from requests import ConnectionError  # noqa: F401

logger = get_task_logger(__name__)
badgrLogger = badgrlog.BadgrLogger()

background_task_queue_name = getattr(settings, "BACKGROUND_TASK_QUEUE_NAME", "default")


@app.task(bind=True, queue=background_task_queue_name)
def rebake_all_assertions(
    self, obi_version=CURRENT_OBI_VERSION, limit=None, offset=0, replay=False
):
    queryset = BadgeInstance.objects.filter(source_url__isnull=True).order_by("pk")
    if limit:
        queryset = queryset[offset : offset + limit]  # noqa: E203
    else:
        queryset = queryset[offset:]
    assertions = queryset.only("entity_id")

    count = 0
    for assertion in assertions:
        rebake_assertion_image.delay(
            assertion_entity_id=assertion.entity_id, obi_version=obi_version
        )
        count += 1

    if limit and replay and count >= limit:
        rebake_all_assertions.delay(
            obi_version=obi_version, limit=limit, offset=offset + limit, replay=True
        )

    return {
        "success": True,
        "count": count,
        "limit": limit,
        "offset": offset,
        "message": "Enqueued {} assertions for rebaking".format(count),
    }


@app.task(bind=True, queue=background_task_queue_name)
def rebake_all_assertions_for_badge_class(
    self,
    badge_class_id,
    obi_version=CURRENT_OBI_VERSION,
    limit=None,
    offset=0,
    replay=False,
):
    queryset = BadgeInstance.objects.filter(
        badgeclass_id=badge_class_id, source_url__isnull=True
    ).order_by("pk")
    if limit:
        queryset = queryset[offset : offset + limit]  # noqa: E203
    else:
        queryset = queryset[offset:]
    assertions = queryset.only("entity_id")

    count = 0
    for assertion in assertions:
        rebake_assertion_image.delay(
            assertion_entity_id=assertion.entity_id, obi_version=obi_version
        )
        count += 1

    if limit and replay and count >= limit:
        rebake_all_assertions_for_badge_class.delay(
            badge_class_id,
            obi_version=obi_version,
            limit=limit,
            offset=offset + limit,
            replay=True,
        )

    return {
        "success": True,
        "count": count,
        "limit": limit,
        "offset": offset,
        "message": "Enqueued {} assertions for rebaking due to badge class change".format(
            count
        ),
    }


@app.task(bind=True, queue=background_task_queue_name)
def rebake_assertion_image(
    self, assertion_entity_id=None, obi_version=CURRENT_OBI_VERSION
):

    try:
        assertion = BadgeInstance.cached.get(entity_id=assertion_entity_id)
    except BadgeInstance.DoesNotExist:
        return {
            "success": False,
            "error": "Unknown assertion entity_id={}".format(assertion_entity_id),
        }

    if assertion.source_url:
        return {
            "success": False,
            "error": "Skipping imported assertion={}  source_url={}".format(
                assertion_entity_id, assertion.source_url
            ),
        }

    assertion.rebake(obi_version=obi_version)

    return {
        "success": True,
        "message": "Rebaked image for {}".format(assertion_entity_id),
    }


@app.task(bind=True, queue=background_task_queue_name)
def update_issuedon_all_assertions(self, start=None, end=None):
    start_date = None
    end_date = None

    # only get assertions that were imported into backpack
    queryset = BadgeInstance.objects.filter(source_url__isnull=False)

    try:
        if start:
            start_date = dateutil.parser.parse(start)
            queryset = queryset.filter(created_at__gte=start_date)

        if end:
            end_date = dateutil.parser.parse(end)
            queryset = queryset.filter(created_at__lte=end_date)
    except ValueError:
        return {"success": False, "start": start, "end": end, "message": "Invalid date"}

    count = 0
    for assertion in queryset:
        update_issuedon_imported_assertion.delay(assertion.entity_id)
        count += 1

    return {
        "success": True,
        "start_date": start_date,
        "end_date": end_date,
        "totalCount": count,
    }


@app.task(bind=True, queue=background_task_queue_name)
def update_issuedon_imported_assertion(self, assertion_entityid):

    try:
        assertion = BadgeInstance.objects.get(entity_id=assertion_entityid)
    except BadgeInstance.DoesNotExist:
        return {
            "success": False,
            "assertion": assertion_entityid,
            "message": "No such assertion.",
        }

    if not assertion.source_url:
        return {
            "success": False,
            "assertion": assertion_entityid,
            "message": "Not an imported assertion.",
        }

    assertion_obo = BadgeCheckHelper.get_assertion_obo(assertion)
    if not assertion_obo:
        return {
            "success": False,
            "assertion": assertion_entityid,
            "message": "Unable to fetch assertion with source_url={}".format(
                assertion.source_url
            ),
        }

    original_issuedOn_date = dateutil.parser.parse(assertion_obo["issuedOn"])
    updated = False

    if original_issuedOn_date != assertion.issued_on:
        assertion.issued_on = original_issuedOn_date
        assertion.save()
        updated = True

    return {
        "success": True,
        "assertion": assertion.entity_id,
        "source_url": assertion.source_url,
        "updated": updated,
    }


@app.task(bind=True, queue=background_task_queue_name)
def remove_backpack_duplicates(
    self, limit=None, offset=0, replay=False, report_only=False
):

    queryset = Issuer.objects.filter(source_url__isnull=False).order_by("pk")
    if limit:
        queryset = queryset[offset : offset + limit]  # noqa: E203
    else:
        queryset = queryset[offset:]

    imported_issuers = queryset.only("entity_id", "source_url")

    count = 0
    for issuer in imported_issuers:
        if resolve_source_url_referencing_local_object(issuer.source_url):
            remove_backpack_duplicate_issuer.delay(
                issuer_entity_id=issuer.entity_id, report_only=report_only
            )
            count += 1

    if limit and replay and count >= limit:
        remove_backpack_duplicates.delay(
            limit=limit, offset=offset + limit, replay=True, report_only=report_only
        )

    return {
        "success": True,
        "count": count,
        "limit": limit,
        "offset": offset,
        "report_only": report_only,
        "message": "Enqueued {} duplicate issuers for removal".format(count),
    }


@app.task(bind=True, queue=background_task_queue_name)
def remove_backpack_duplicate_issuer(self, issuer_entity_id=None, report_only=False):
    try:
        issuer = Issuer.objects.get(entity_id=issuer_entity_id)
    except Issuer.DoesNotExist:
        return {
            "success": False,
            "message": "No such issuer",
            "issuer_entity_id": issuer_entity_id,
        }

    if not resolve_source_url_referencing_local_object(issuer.source_url):
        return {
            "success": False,
            "message": "Not a duplicate issuer",
            "issuer_entity_id": issuer_entity_id,
        }

    assertions = issuer.badgeinstance_set.all()
    badgeclasses = issuer.badgeclasses.all()

    # ensure this issuer doesn't own any non-duplicate objects
    for badgeclass in badgeclasses:
        if not resolve_source_url_referencing_local_object(badgeclass.source_url):
            return {
                "success": False,
                "message": "A non-duplicate badgeclass was found owned by this issuer.",
                "issuer_entity_id": issuer_entity_id,
                "badgeclass_entity_id": badgeclass.entity_id,
            }
    for assertion in assertions:
        if not resolve_source_url_referencing_local_object(assertion.source_url):
            return {
                "success": False,
                "message": "A non-duplicate assertion was found owned by this issuer.",
                "issuer_entity_id": issuer_entity_id,
                "assertion_entity_id": assertion.entity_id,
            }

    assertion_count = 0
    badgeclass_count = 0
    if not report_only:
        # purge assertions, then badgeclasses, then the issuer

        for assertion in assertions:
            assertion.delete()
            assertion_count += 1

        for badgeclass in badgeclasses:
            badgeclass.delete()
            badgeclass_count += 1

        issuer.delete()

    return {
        "success": True,
        "message": "Duplicate Issuer Report" if report_only else "Issuer removed.",
        "issuer_entity_id": issuer_entity_id,
        "badgeclass_count": badgeclass_count,
        "assertion_count": assertion_count,
    }


@app.task(bind=True, queue=background_task_queue_name)
def resend_notifications(self, badgeinstance_entity_ids):
    current = 0
    page = 100
    while len(badgeinstance_entity_ids[current : current + page]):  # noqa: E203
        queryset = BadgeInstance.objects.filter(
            entity_id__in=badgeinstance_entity_ids[
                current : current + page  # noqa: E203
            ]
        )
        for bi in queryset:
            bi.notify_earner(renotify=True)
        current = current + page

    return {
        "success": True,
        "message": "{} notification requests processed".format(
            len(badgeinstance_entity_ids)
        ),
        "entity_ids": badgeinstance_entity_ids,
    }


@app.task(bind=True, queue=background_task_queue_name)
def generate_png_preview_image(self, entity_id, entity_type):
    # Get instance of entity we are creating PNG preview for
    if entity_type == BadgeClass.__name__:
        entity = BadgeClass.objects.get(id=entity_id)
    elif entity_type == Issuer.__name__:
        entity = Issuer.objects.get(id=entity_id)
    else:
        return {
            "success": False,
            "message": "Unknown entity type.",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    # Check if a preview image already exists
    if entity.image_preview:
        return {
            "success": True,
            "message": "Image preview already exists on entity.",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    # Verify that this entity's image is an SVG
    if not verify_svg(entity.image):
        return {
            "success": False,
            "message": "Image on entity is not an SVG.",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    max_square = getattr(settings, "IMAGE_FIELD_MAX_PX", 400)

    # Do the conversion call
    png_bytes = convert_svg_to_png(entity.image.read(), max_square, max_square)

    if not png_bytes:
        return {
            "success": False,
            "message": "Error converting SVG to PNG",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    png_preview_name = "%s.png" % os.path.splitext(entity.image.name)[0]
    entity.image_preview = InMemoryUploadedFile(
        png_bytes, None, png_preview_name, "image/png", png_bytes.tell(), None
    )
    entity.save()
    return {
        "success": True,
        "message": "PNG preview created from SVG",
        "entity_type": entity_type,
        "entity_id": entity_id,
    }


def handle_png_preview_post_save(sender, instance, **kwargs):
    if not getattr(settings, "SVG_HTTP_CONVERSION_ENABLED", False):
        return

    # If instance doesn't have an image preview and its image is an SVG, generate PNG image_preview copy.
    if not instance.image_preview and instance.image and verify_svg(instance.image):
        generate_png_preview_image.delay(
            entity_id=instance.id, entity_type=type(instance).__name__
        )


post_save.connect(handle_png_preview_post_save, sender=Issuer)
post_save.connect(handle_png_preview_post_save, sender=BadgeClass)
