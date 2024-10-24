from django.core.management.base import BaseCommand
from badgeuser.models import BadgeUser

class Command(BaseCommand):
    def handle(self, *args, **options):
        user = BadgeUser.objects.filter(email="").first()
        self.stdout.write("Updating user: {}".format(user))
        user.termsagreement_set.get_or_create(terms_version=1)
        self.stdout.write("tos updated: {}".format(user.agreed_terms_version))
        user.save()

