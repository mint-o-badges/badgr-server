from django.core.management.base import BaseCommand
from django.utils import timezone
from mainsite.models import AccessTokenProxy, AccessTokenScope


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Splitting all scopes on tokens")

        chunk_size = 5000
        page = 0

        self.stdout.write("Deleting AccessTokenScopes")
        AccessTokenScope.objects.all().delete()

        self.stdout.write("Bulk creating AccessTokenScope")
        while True:
            tokens = AccessTokenProxy.objects.filter(expires__gt=timezone.now())[
                page : page + chunk_size  # noqa: E203
            ]
            for t in tokens:
                scopes = []
                for s in t.scope.split():
                    scopes.append(AccessTokenScope(scope=s, token=t))

                AccessTokenScope.objects.bulk_create(scopes)
            if len(tokens) < chunk_size:
                break
            page += chunk_size

        self.stdout.write("All done.")
