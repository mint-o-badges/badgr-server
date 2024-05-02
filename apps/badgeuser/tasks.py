import badgrlog
from celery.utils.log import get_task_logger
from django.conf import settings
from mainsite.celery import app

logger = get_task_logger(__name__)
badgrLogger = badgrlog.BadgrLogger()

email_task_queue_name = getattr(settings, "BACKGROUND_TASK_QUEUE_NAME", "default")


@app.task(bind=True, queue=email_task_queue_name)
def process_email_verification(self, email_address_id):
    from badgeuser.models import CachedEmailAddress
    from issuer.models import BadgeInstance

    try:
        email_address = CachedEmailAddress.cached.get(id=email_address_id)
    except CachedEmailAddress.DoesNotExist:
        return

    user = email_address.user
    issuer_instances = BadgeInstance.objects.filter(
        recipient_identifier=email_address.email
    )
    variants = list(email_address.cached_variants())

    for i in issuer_instances:
        if (
            i.recipient_identifier not in variants
            and i.recipient_identifier != email_address.email
            and user.can_add_variant(i.recipient_identifier)
        ):
            email_address.add_variant(i.recipient_identifier)


@app.task(bind=True, queue=email_task_queue_name)
def process_post_recipient_id_verification_change(self, identifier, type, verified):
    from issuer.models import BadgeInstance, get_user_or_none

    if verified:
        user = get_user_or_none(identifier, type)
        if user:
            BadgeInstance.objects.filter(recipient_identifier=identifier).update(
                user=user
            )
    else:
        BadgeInstance.objects.filter(recipient_identifier=identifier).update(user=None)
    for b in BadgeInstance.objects.filter(recipient_identifier=identifier):
        b.publish()


@app.task(bind=True, queue=email_task_queue_name)
def process_post_recipient_id_deletion(self, identifier):
    from issuer.models import BadgeInstance

    BadgeInstance.objects.filter(recipient_identifier=identifier).update(user=None)
    for b in BadgeInstance.objects.filter(recipient_identifier=identifier):
        b.publish()
