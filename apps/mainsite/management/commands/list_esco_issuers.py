from json import loads
from django.core.management.base import BaseCommand
from issuer.models import BadgeClass
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        issuerArray = []
        badgesArray = []
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
                            escoID = item.get('escoID')
                            if escoID is not None and escoID != '': 
                                print("competency_dict: ", competency_dict)
                                issuer = badgeclass.issuer
                                issuerArray.append(issuer.name)
                                badgesArray.append(badgeclass.entity_id)
                issuerSet = set(issuerArray)
                badgesSet = set(badgesArray)
                f.write(f"IssuerName: {issuerSet}, BadgeClass {badgesSet}  \n")                                

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
        
