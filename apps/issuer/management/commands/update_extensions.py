import json
from django.core.management import BaseCommand
from issuer.models import BadgeClass, BadgeClassExtension
from json import loads
from django.db import transaction

class Command(BaseCommand):

    escoBaseURl: str = 'http://data.europa.eu'
    def handle(self, *args, **options):
        with transaction.atomic():

            badgeclasses = BadgeClass.objects.all()

            for badgeclass in badgeclasses:
                extensions = badgeclass.get_extensions_manager()

                competency_extension = extensions.filter(name='extensions:CompetencyExtension').first()
                if competency_extension is not None:
                    competency_json = competency_extension.original_json
                    competency_dict = loads(competency_json)
                    self.stdout.write("Updating competency {}".format(competency_dict.get('name')))
                    for item in competency_dict: 
                        escoID = item.get('escoID')
                        if escoID is not None: 
                            item['framework'] = 'esco'
                            item['source'] = 'ai'
                            item['framework-identifier']= escoID if escoID.startswith('http') else self.escoBaseURl + escoID
                            del item['escoID']
                        else:
                            item['framework'] = ''
                            item['source'] = 'manual'  
                            item['framework-identifier']= ''

                    updated_competency_json = json.dumps(competency_dict)  
                    competency_extension.original_json = updated_competency_json
                    competency_extension.save()               