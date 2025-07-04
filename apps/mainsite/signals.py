from mainsite.models import AccessTokenScope


def handle_token_save(sender, instance=None, **kwargs):
    for s in instance.scope.split():
        AccessTokenScope.objects.get_or_create(token=instance, scope=s)
