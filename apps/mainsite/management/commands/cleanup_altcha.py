from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from mainsite.models import AltchaChallenge


class Command(BaseCommand):
    help = "Cleanup old Altcha challenges"

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(hours=24)
        old_challenges = AltchaChallenge.objects.filter(created_at__lt=cutoff)
        count = old_challenges.count()
        old_challenges.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {count} old challenges")
        )
