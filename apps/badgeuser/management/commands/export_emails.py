import csv
import os

from badgeuser.models import BadgeUser
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        users = BadgeUser.objects.all()
        file_path = os.path.join(os.getcwd(), "user_emails.csv")
        try:
            with open(file_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Vorname", "Nachname", "E-Mail"])

                for user in users:
                    writer.writerow(
                        [user.first_name, user.last_name, user.primary_email]
                    )
            self.stdout.write(
                self.style.SUCCESS(f"Successfully exported emails to {file_path}")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
