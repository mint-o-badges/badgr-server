from allauth.account.adapter import get_adapter
from django.core.management.base import BaseCommand
from issuer.models import RequestedBadge


class Command(BaseCommand):
    """Send mail to issuer staff when badges were requested via qr code"""

    help = "Send mail to issuer staff when badges were requested via qr code that day"

    def handle(self, *args, **kwargs):

        requested_badges = RequestedBadge.objects.filter()

        for badge in requested_badges:
            for member in badge.qrcode.issuer.cached_issuerstaff():
                if badge.qrcode.notifications:
                    ctx = {
                        "badge_name": badge.badgeclass.name,
                        "call_to_action_label": "Anfrage bestätigen",
                    }
                    get_adapter().send_mail(
                        "account/email/email_badge_request",
                        member.cached_user.email,
                        ctx,
                    )

        self.stdout.write(self.style.SUCCESS("Successfully sent emails"))
