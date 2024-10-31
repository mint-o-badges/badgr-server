from json import loads
from django.core.management.base import BaseCommand
from issuer.models import BadgeClass
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        issuerArray = []
        badgeclasses = BadgeClass.objects.all()

        file_path = os.path.join(os.getcwd(), 'issuers.txt')
        try:
            with open(file_path, 'w') as f:
                for badgeclass in badgeclasses:
                    extensions = badgeclass.get_extensions_manager()

                    competency_extension = extensions.filter(name='extensions:CompetencyExtension').first()
                    if competency_extension is not None:
                        competency_json = competency_extension.original_json
                        competency_dict = loads(competency_json)
                        for item in competency_dict: 
                            escoID = item.get('framework_identifier')
                            if escoID is not None and escoID != '': 
                                issuer = badgeclass.issuer
                                issuerArray.append(issuer)
                                f.write(f"Name: {issuer.name}, Creator {issuer.cached_creator.email}  \n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
        
