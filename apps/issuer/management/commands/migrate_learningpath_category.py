import json
from django.core.management import BaseCommand
from issuer.models import BadgeClass
from json import loads
from django.db import transaction


class Command(BaseCommand):
    help = 'Update the category extensions of existing learningpath participation badges to the new learningpath category'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate the changes')
        parser.add_argument('--output-file', type=str, default='lp_category.json',
                          help='File to write the changes to during dry run')
        
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        output_file = options['output_file']
        changes_log = []

        with transaction.atomic():
            badgeclasses = BadgeClass.objects.filter(learningpath__isnull=False).distinct()

            for badgeclass in badgeclasses:
                extensions = badgeclass.get_extensions_manager()
                category_extension = extensions.filter(name='extensions:CategoryExtension').first()

                if category_extension is not None:
                    original_json = category_extension.original_json
                    category_dict = loads(original_json)

                    category = category_dict['Category']
                    if category == "participation":
                        category_dict['Category'] = 'learningpath'

                    updated_category_json = json.dumps(category_dict, indent=4)

                    if dry_run:
                        change_entry = {
                            'badgeclass_name': badgeclass.name,
                            'before': json.loads(original_json),
                            'after': json.loads(updated_category_json)
                        }
                        changes_log.append(change_entry)
                        self.stdout.write(f'DRY-RUN: Logged changes for badgeclass {badgeclass.name}')
                    else:
                        category_extension.original_json = updated_category_json
                        category_extension.save()

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