from django.core.management.base import BaseCommand
from issuer.models import BadgeClass, BadgeInstance
from json import loads


class Command(BaseCommand):
    help = "Count badges and assertions by category"

    def handle(self, *args, **options):
        badgeclasses = BadgeClass.objects.all()
        badgeinstances = BadgeInstance.objects.all()

        participation_count = 0
        competency_count = 0
        md_count = 0
        uncategorized_count = 0

        for badgeclass in badgeclasses:
            extensions = badgeclass.get_extensions_manager()
            category_extension = extensions.filter(
                name="extensions:CategoryExtension"
            ).first()

            if category_extension is not None:
                try:
                    original_json = category_extension.original_json
                    category = loads(original_json)["Category"]

                    if category == "participation":
                        participation_count += 1
                    elif category == "competency":
                        competency_count += 1
                    elif category == "learningpath":
                        md_count += 1
                    else:
                        uncategorized_count += 1

                except (KeyError, ValueError) as e:
                    uncategorized_count += 1
            else:
                uncategorized_count += 1
                print(f"No category extension found for badge: {badgeclass.name}")

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("BADGE COUNT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Participation badges: {participation_count}")
        self.stdout.write(f"Competency badges: {competency_count}")
        self.stdout.write(f"MD badges: {md_count}")
        self.stdout.write(f"Uncategorized badges: {uncategorized_count}")

        participation_instances = 0
        competency_instances = 0
        md_instances = 0
        uncategorized_instances = 0

        for instance in badgeinstances:
            badgeclass = instance.badgeclass
            extensions = badgeclass.get_extensions_manager()
            category_extension = extensions.filter(
                name="extensions:CategoryExtension"
            ).first()

            if category_extension is not None:
                try:
                    original_json = category_extension.original_json
                    category = loads(original_json)["Category"]

                    if category == "participation":
                        participation_instances += 1
                    elif category == "competency":
                        competency_instances += 1
                    elif category == "learningpath":
                        md_instances += 1
                    else:
                        uncategorized_instances += 1
                except (KeyError, ValueError):
                    uncategorized_instances += 1
            else:
                uncategorized_instances += 1

        self.stdout.write(self.style.SUCCESS("\nBADGE INSTANCE COUNT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Participation instances: {participation_instances}")
        self.stdout.write(f"Competency instances: {competency_instances}")
        self.stdout.write(f"MD instances: {md_instances}")
        self.stdout.write(f"Uncategorized instances: {uncategorized_instances}")
