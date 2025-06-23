from issuer.models import BadgeClass
from django.core.management import BaseCommand

class Command(BaseCommand):
    help = 'Migrate the data from criteria_url and criteria_text to the new criteria json field'
    
    def handle(self, *args, **options):
    
        for badge in BadgeClass.objects.all():
            if badge.criteria_url:
                badge.criteria = {
                    "id": badge.criteria_url,
                    "criteria": []
                }
            elif badge.criteria_text:
                badge.criteria = {
                    "narrative": badge.criteria_text,
                    "criteria": []
                }
            badge.save()