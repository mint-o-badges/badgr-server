import json
from django.core.management import BaseCommand
from issuer.models import BadgeClass, BadgeClassExtension
from json import loads
from django.db import transaction
from urllib.parse import urlparse, parse_qs


class Command(BaseCommand):

    help = 'Update the competency extensions of a badgeclass to our new format'

    escoBaseURl: str = 'http://data.europa.eu'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate the changes')

    def calculate_FrameworkIdentifier(self, escoId: str) -> str:
                if escoId.startswith(self.escoBaseURl):
                    return escoId
                elif escoId.startswith('https://esco.ec.europa.eu'):
                    parsed_url = urlparse(escoId)
                    query_params = parse_qs(parsed_url.query)
                    uri = query_params.get('uri', [None])[0]
                    return uri
                elif escoId.startswith('/skill/'):
                    return self.escoBaseURl + '/esco' + escoId
                else:
                    return self.escoBaseURl + escoId    

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        with transaction.atomic():

            badgeclasses = BadgeClass.objects.all()                

            for badgeclass in badgeclasses:
                extensions = badgeclass.get_extensions_manager()

                competency_extension = extensions.filter(name='extensions:CompetencyExtension').first()
                if competency_extension is not None:
                    competency_json = competency_extension.original_json
                    competency_dict = loads(competency_json)
                    for item in competency_dict: 
                        escoID = item.get('escoID')
                        if escoID is not None and escoID != '': 
                            item['framework'] = 'esco'
                            item['source'] = 'ai'
                            item['framework_identifier']= self.calculate_FrameworkIdentifier(escoID)
                            del item['escoID']
                        elif escoID == '':
                            item['framework'] = ''
                            item['source'] = 'manual'  
                            item['framework_identifier']= ''
                            del item['escoID']

                    updated_competency_json = json.dumps(competency_dict, indent=4)  
                    competency_extension.original_json = updated_competency_json
                    if dry_run:
                        self.stdout.write(f'DRY-RUN: Would update competencies in badgeclass {badgeclass.name}:\n {updated_competency_json}')
                    else:
                        competency_extension.save()               