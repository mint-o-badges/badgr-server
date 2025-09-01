from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from mainsite.models import IframeUrl


class Command(BaseCommand):
    help = "Cleanup old iframe URLs"

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(hours=24)
        old_iframe_urls = IframeUrl.objects.filter(created_at__lt=cutoff)
        count = old_iframe_urls.count()
        old_iframe_urls.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {count} old iframe URLs")
        )
