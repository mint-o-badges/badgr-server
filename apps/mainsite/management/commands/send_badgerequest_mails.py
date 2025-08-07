from datetime import date, timedelta

from allauth.account.adapter import get_adapter
from django.core.management.base import BaseCommand
from issuer.models import QrCode, RequestedBadge


class Command(BaseCommand):
    """Send mail to issuer staff when badges were requested via qr code"""

    help = "Send mail to issuer staff when badges were requested via qr code that day"

    def handle(self, *args, **kwargs):
        # qr codes that have been created prior to implementation of the notification feature
        # do not have the created_by_user field set and are therefore skipped
        qr_codes = QrCode.objects.filter(
            notifications=True, created_by_user__isnull=False
        )
        self.stdout.write(
            "Total number of notifiable qr codes with active notifications: "
            + str(len(qr_codes))
        )

        for qr in qr_codes:
            # this command is intended to run once a day after midnight,
            # so only those badges that have been request in the last 24 hours
            # are relevant when we decide whether or not to send out an email.
            # this prevents flooding the user with daily mails even though no new
            # requests came in.
            reference_date = date.today() - timedelta(days=1)
            if (
                len(
                    RequestedBadge.objects.filter(
                        qrcode=qr, requestedOn__gt=reference_date
                    )
                )
                > 0
            ):
                request_url = (
                    f"https://openbadges.education/issuer/issuers/{qr.issuer.entity_id}"
                    f"/badges/{qr.badgeclass.entity_id}?focusRequests=true"
                )

                ctx = {
                    "badge_name": qr.badgeclass.name,
                    "number_of_open_requests": len(
                        RequestedBadge.objects.filter(qrcode=qr)
                    ),
                    "activate_url": request_url,
                    "call_to_action_label": "Anfrage bestätigen",
                }
                get_adapter().send_mail(
                    "account/email/email_badge_request",
                    qr.created_by_user.email,
                    ctx,
                )
                self.stdout.write("QR " + str(qr.entity_id) + " notification was sent")
            else:
                self.stdout.write(
                    "QR "
                    + str(qr.entity_id)
                    + " does not have any requests to notify about"
                )

        self.stdout.write(self.style.SUCCESS("Successfully sent emails"))
