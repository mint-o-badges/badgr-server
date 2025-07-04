from json import loads
from django.core.management.base import BaseCommand
from issuer.models import BadgeClass
import os


class Command(BaseCommand):
    def handle(self, *args, **options):
        # Structure: {issuer_name: {badge_id: [esco_ids]}}
        issuer_data = {}

        badgeclasses = BadgeClass.objects.all()

        file_path = os.path.join(os.getcwd(), "esco_issuers.txt")
        try:
            for badgeclass in badgeclasses:
                extensions = badgeclass.get_extensions_manager()
                competency_extension = extensions.filter(
                    name="extensions:CompetencyExtension"
                ).first()

                if competency_extension is not None:
                    competency_json = competency_extension.original_json
                    competency_dict = loads(competency_json)

                    esco_ids = []
                    for item in competency_dict:
                        escoID = item.get("escoID")
                        if escoID is not None and escoID != "":
                            esco_ids.append(escoID)

                    if esco_ids:
                        issuer_name = badgeclass.issuer.name
                        badge_id = badgeclass.entity_id

                        if issuer_name not in issuer_data:
                            issuer_data[issuer_name] = {}

                        issuer_data[issuer_name][badge_id] = esco_ids

            with open(file_path, "w") as f:
                for issuer_name, badges_data in issuer_data.items():
                    f.write(f"\nIssuer: {issuer_name}\n")
                    f.write("Badges and their Competencies:\n")

                    for badge_id, esco_ids in badges_data.items():
                        f.write(f"  - Badge ID: {badge_id}\n")
                        f.write("    ESCO IDs:\n")
                        for esco_id in esco_ids:
                            f.write(f"      * {esco_id}\n")

                    f.write("-" * 50 + "\n")

                self.stdout.write(
                    self.style.SUCCESS("Successfully wrote grouped badge data to file")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
