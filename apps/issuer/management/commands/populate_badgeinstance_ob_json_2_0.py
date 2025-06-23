# encoding: utf-8
import json
from django.core.management import BaseCommand

from issuer.models import BadgeInstance

class Command(BaseCommand):

    def handle(self, *args, **options):

      for bi in BadgeInstance.objects.all():
         if not bi.ob_json_2_0:
            bi.ob_json_2_0 = json.dumps(bi.get_json_2_0())
            bi.save(update_fields=['ob_json_2_0'])

      self.stdout.write("Finished populating BadgeInstance.ob_json_2_0")
