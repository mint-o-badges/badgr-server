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
        parser.add_argument('--output-file', type=str, default='competency_changes.json',
                          help='File to write the changes to during dry run')

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
        output_file = options['output_file']
        changes_log = []

        with transaction.atomic():
            badgeclasses = BadgeClass.objects.all()

            for badgeclass in badgeclasses:
                extensions = badgeclass.get_extensions_manager()
                competency_extension = extensions.filter(name='extensions:CompetencyExtension').first()

                if competency_extension is not None:
                    original_json = competency_extension.original_json
                    competency_dict = loads(original_json)

                    for item in competency_dict:
                        escoID = item.get('escoID')
                        if escoID is not None and escoID != '':
                            item['framework'] = 'esco'
                            item['source'] = 'ai'
                            item['framework_identifier'] = self.calculate_FrameworkIdentifier(escoID)
                            del item['escoID']
                        elif escoID == '':
                            item['framework'] = ''
                            item['source'] = 'manual'
                            item['framework_identifier'] = ''
                            del item['escoID']

                    updated_competency_json = json.dumps(competency_dict, indent=4)

                    if dry_run:
                        change_entry = {
                            'badgeclass_name': badgeclass.name,
                            'before': json.loads(original_json),
                            'after': json.loads(updated_competency_json)
                        }
                        changes_log.append(change_entry)
                        self.stdout.write(f'DRY-RUN: Logged changes for badgeclass {badgeclass.name}')
                    else:
                        competency_extension.original_json = updated_competency_json
                        competency_extension.save()

        if dry_run and changes_log:
            try:
                with open(output_file, 'w') as f:
                    json.dump(changes_log, f, indent=4)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully wrote changes to {output_file}'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed to write to {output_file}: {str(e)}'
                    )
                )           