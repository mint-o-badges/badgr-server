import logging
logger = logging.getLogger("Badgr.Events")

def log_user_signed_up(sender, **kwargs):
    logger.debug("User '%s' signed up", kwargs.get("user").username)


def log_email_confirmed(sender, **kwargs):
    logger.debug("Confirmed email '%s'", kwargs.get("email_address").email)


def handle_email_created(sender, instance=None, created=False, **kwargs):
    """
    SocialLogin.save saves the user before creating EmailAddress objects. In cases
    where the user is not otherwise updated during the login / signup flow, this
    leaves user.cached_emails() empty.
    """
    if created:
        instance.user.publish_method("cached_emails")
