from django.core.management.base import BaseCommand
from badgeuser.models import BadgeUser
from allauth.account.adapter import get_adapter
# from badgeuser.utils import notify_tos_confirmation


class Command(BaseCommand):
    args = ''
    help = 'Send Email to all users to confirm the new terms of service'

    def handle(self, *args, **options):
        for user in BadgeUser.objects.all():
            if user.agreed_terms_version != 2:
                get_adapter().send_tos_confirmation(email=user.email, tos_version=2)
