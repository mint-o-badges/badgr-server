import badgrlog

badgrlogger = badgrlog.BadgrLogger()


def log_user_signed_up(sender, **kwargs):
    badgrlogger.event(badgrlog.UserSignedUp(**kwargs))


def log_email_confirmed(sender, **kwargs):
    badgrlogger.event(badgrlog.EmailConfirmed(**kwargs))


def handle_email_created(sender, instance=None, created=False, **kwargs):
    """
    SocialLogin.save saves the user before creating EmailAddress objects. In cases
    where the user is not otherwise updated during the login / signup flow, this
    leaves user.cached_emails() empty.
    """
    if created:
        instance.user.publish_method("cached_emails")
