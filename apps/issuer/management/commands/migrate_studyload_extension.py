import json
import math
from django.core.management import BaseCommand
from issuer.models import BadgeClass
from json import loads
from django.db import transaction


class Command(BaseCommand):
    help = 'Update the studyload of competencies to include hours and minutes'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate the changes')
        parser.add_argument('--output-file', type=str, default='competency_studyload_changes.json',
                          help='File to write the changes to during dry run')

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
                        studyload = item.get('studyLoad')
                        minutes = item.get('minutes')
                        hours = item.get('hours')

                        if studyload is not None and minutes is None and hours is None:
                            hours = math.floor(studyload / 60) if studyload > 59 else 0
                            minutes = math.floor(studyload % 60)
                            item['minutes'] = minutes
                            item['hours'] = hours

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