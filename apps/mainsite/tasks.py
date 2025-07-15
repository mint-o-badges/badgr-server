from celery import shared_task
from issuer.models import LearningPath
from badgeuser.models import BadgeUser


@shared_task
def process_learning_path_activation(pk):
    """
    Process Micro-Degree-Badge issuance for all users when a learning path is activated.
    """

    try:
        learning_path = LearningPath.objects.get(pk=pk)

        for user in BadgeUser.objects.all():
            for identifier in user.all_verified_recipient_identifiers:
                if learning_path.user_should_have_badge(identifier):
                    learning_path.participationBadge.issue(
                        recipient_id=identifier,
                        notify=True,
                        microdegree_id=learning_path.entity_id,
                    )

        return f"Successfully processed learning path activation for {pk}"

    except LearningPath.DoesNotExist:
        return f"LearningPath with pk {pk} not found"
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error processing learning path activation {pk}: {str(e)}")
        raise
