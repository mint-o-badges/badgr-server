import json
from django.core.management import BaseCommand
from issuer.models import BadgeClass
from django.db import transaction


class Command(BaseCommand):
    help = 'Remove the content from the criteria_text field'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate the changes')
        parser.add_argument('--output-file', type=str, default='criteria_changes.json',
                          help='File to write the changes to during dry run')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        output_file = options['output_file']
        changes_log = []

        with transaction.atomic():
            badgeclasses = BadgeClass.objects.all()

            for badgeclass in badgeclasses:
                if badgeclass.criteria_text is not None: 
                    badgeclass.criteria_text = None
                    badgeclass.save()

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