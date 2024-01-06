# encoding: utf-8


from django.core.management import BaseCommand

from badgeuser.models import CachedEmailAddress, UserRecipientIdentifier
from issuer.models import BadgeInstance


class Command(BaseCommand):
    def handle(self, *args, **options):

        self.stdout.write("Updating BadgeInstaces...")
        self.stdout.write("1. Setting users from verified CachedEmailAddress")
        for verified_id in CachedEmailAddress.objects.filter(verified=True):
            self.update(verified_id.user, verified_id.email)

        self.stdout.write("2. Setting users from verified UserRecipientIdentifier")
        for verified_id in UserRecipientIdentifier.objects.filter(verified=True):
            self.update(verified_id.user, verified_id.identifier)

        # Trigger cache updates
        chunk_size = 500
        page = 0

        self.stdout.write("3. Triggering cache updates")
        while True:
            badges = BadgeInstance.objects.filter(user__isnull=False)[page:page + chunk_size]
            self.stdout.write("Processing badges %d through %d" % (page + 1, page + len(badges)))
            for b in badges:
                b.publish()
            if len(badges) < chunk_size:
                break
            page = page + chunk_size

        self.stdout.write("All done.")

    def update(self, user, identifier):
        BadgeInstance.objects.filter(recipient_identifier=identifier).update(user=user)
